import asyncio
import base64
import json
import logging
import wave
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

import cv2
import numpy as np
from google.genai import types as genai_types

from live_config import (
    BASE_DIR,
    MODEL,
    RECEIVE_SAMPLE_RATE,
    SEND_SAMPLE_RATE,
    build_live_config,
    client,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FINAL_SIGNOFF_PHRASES = (
    "i hope you have a great day",
    "have a great day",
    "enjoy the rest of your day",
)

app = FastAPI(title="Live Interview API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/")
async def home() -> Dict[str, str]:
    return {"status": "ok"}


class WebSocketInterviewSession:
    def __init__(self, websocket: WebSocket, resume_handle: Optional[str] = None) -> None:
        self.websocket = websocket
        self.session = None
        self._tasks = []
        haar_dir = BASE_DIR / "haarcascades"
        self._face_cascade = cv2.CascadeClassifier(
            str(haar_dir / "haarcascade_frontalface_default.xml")
        )
        self._looked_away = 0
        self._looked_away_warnings = 0
        self._lookaway_threshold = 10
        self._max_warnings = 3
        self._session_terminated = False
        self._resume_handle = resume_handle
        self._assistant_chunks: bytearray = bytearray()
        self._candidate_chunks: bytearray = bytearray()
        self._recordings_dir = BASE_DIR / "recordings"
        self._recordings_dir.mkdir(exist_ok=True)
        self._session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._session_prefix = f"session_{self._session_id}"
        self._audio_lock = asyncio.Lock()
        self._mic_lock = asyncio.Lock()
        self._transcripts: List[Dict[str, Any]] = []
        self._shutdown_reason: Optional[str] = None

    async def run(self) -> None:
        await self.websocket.accept()
        try:
            config = build_live_config(self._resume_handle)

            async with client.aio.live.connect(model=MODEL, config=config) as session:
                self.session = session

                await session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{"text": "--SYSTEM-- Candidate Joined the call."}],
                    },
                    turn_complete=True,
                )

                await self.websocket.send_json(
                    {
                        "type": "status",
                        "status": "ready",
                        "sendSampleRate": SEND_SAMPLE_RATE,
                        "receiveSampleRate": RECEIVE_SAMPLE_RATE,
                        "resumeHandle": self._resume_handle,
                    }
                )

                forward_task = asyncio.create_task(self._forward_client_messages())
                backward_task = asyncio.create_task(self._forward_model_responses())
                self._tasks = [forward_task, backward_task]

                done, pending = await asyncio.wait(
                    self._tasks,
                    return_when=asyncio.FIRST_EXCEPTION,
                )

                for task in pending:
                    task.cancel()

                for task in done:
                    task.result()
        finally:
            logger.info(
                "Session %s closing (reason=%s)",
                self._session_id,
                self._shutdown_reason or "normal",
            )
            await self._flush_recordings()
            await self._safe_close()

    async def _flush_recordings(self) -> None:
        assistant_pcm: bytes = b""
        candidate_pcm: bytes = b""
        async with self._audio_lock:
            if self._assistant_chunks:
                assistant_pcm = bytes(self._assistant_chunks)
                self._assistant_chunks.clear()
        async with self._mic_lock:
            if self._candidate_chunks:
                candidate_pcm = bytes(self._candidate_chunks)
                self._candidate_chunks.clear()

        transcripts: List[Dict[str, Any]] = []
        if self._transcripts:
            transcripts = list(self._transcripts)
            self._transcripts.clear()

        assistant_path = self._recordings_dir / f"{self._session_prefix}_assistant.wav"
        candidate_path = self._recordings_dir / f"{self._session_prefix}_candidate.wav"
        mix_path = self._recordings_dir / f"{self._session_prefix}_mix.wav"
        transcripts_path = self._recordings_dir / f"{self._session_prefix}_transcripts.jsonl"

        tasks = []
        if assistant_pcm:
            tasks.append(
                asyncio.to_thread(
                    self._write_wav,
                    assistant_path,
                    assistant_pcm,
                    RECEIVE_SAMPLE_RATE,
                )
            )
        if candidate_pcm:
            tasks.append(
                asyncio.to_thread(
                    self._write_wav,
                    candidate_path,
                    candidate_pcm,
                    SEND_SAMPLE_RATE,
                )
            )
        if assistant_pcm and candidate_pcm:
            tasks.append(
                asyncio.to_thread(
                    self._mix_wavs,
                    assistant_path,
                    candidate_path,
                    mix_path,
                )
            )
        if transcripts:
            tasks.append(
                asyncio.to_thread(
                    self._write_transcripts,
                    transcripts_path,
                    transcripts,
                )
            )

        if not tasks:
            return

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            "Session %s recordings saved: assistant=%s candidate=%s transcripts=%s",
            self._session_id,
            assistant_path.exists(),
            candidate_path.exists(),
            transcripts_path.exists() if transcripts else False,
        )

        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.send_json(
                {
                    "type": "recordings",
                    "sessionId": self._session_id,
                    "assistantPath": str(assistant_path) if assistant_pcm else None,
                    "candidatePath": str(candidate_path) if candidate_pcm else None,
                    "mixPath": str(mix_path) if assistant_pcm and candidate_pcm else None,
                    "transcriptsPath": str(transcripts_path) if transcripts else None,
                }
            )

    async def _forward_client_messages(self) -> None:
        assert self.session is not None
        while True:
            if self._shutdown_reason:
                break
            try:
                message = await self.websocket.receive()
            except WebSocketDisconnect:
                await self._finalize_session("client_disconnected")
                break

            if message["type"] == "websocket.disconnect":
                break

            if message["type"] != "websocket.receive":
                continue

            payload: Dict[str, Any]
            if "text" in message:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON message from client: %s", message["text"])
                    continue
            elif "bytes" in message:
                try:
                    payload = json.loads(message["bytes"].decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    logger.warning("Invalid bytes message from client")
                    continue
            else:
                continue

            msg_type = payload.get("type")
            if msg_type == "audio":
                data = payload.get("data")
                if not data:
                    continue
                try:
                    pcm = base64.b64decode(data)
                except (TypeError, ValueError):
                    logger.warning("Failed to decode audio payload")
                    continue
                async with self._mic_lock:
                    self._candidate_chunks.extend(pcm)
                await self.session.send_realtime_input(
                    media={"data": pcm, "mime_type": "audio/pcm"}
                )
            elif msg_type == "image":
                media = payload.get("data")
                mime_type = payload.get("mime_type", "image/jpeg")
                if media:
                    await self._process_frame(media)
                    await self.session.send_realtime_input(
                        media={"data": media, "mime_type": mime_type}
                    )
            elif msg_type == "text":
                text = payload.get("text", "")
                turn_complete = payload.get("turn_complete", True)
                await self.session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{"text": text or "."}],
                    },
                    turn_complete=turn_complete,
                )
            elif msg_type == "control" and payload.get("action") == "stop":
                await self.session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{"text": "--SYSTEM-- Session terminated by client."}],
                    },
                    turn_complete=True,
                )
                await self._finalize_session("client_stop")
                break

    async def _process_frame(self, base64_frame: str) -> None:
        if self._face_cascade.empty() or self._session_terminated:
            return
        try:
            frame_bytes = base64.b64decode(base64_frame)
        except (TypeError, ValueError):
            logger.warning("Failed to decode frame payload")
            return

        np_arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, 1.3, 4)

        if len(faces) >= 1:
            self._looked_away = 0
        else:
            self._looked_away += 1

        if self._looked_away > self._lookaway_threshold:
            self._looked_away_warnings += 1
            self._looked_away = 0
            await self.session.send_client_content(
                turns={
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"--SYSTEM-- User looking away - warn the candidate it's the "
                                f"{self._looked_away_warnings} time(s) and "
                                f"{self._max_warnings - self._looked_away_warnings} warning(s) left."
                            )
                        }
                    ],
                },
                turn_complete=True,
            )
            await self.websocket.send_json(
                {
                    "type": "monitor",
                    "event": "look_away_warning",
                    "warnings": self._looked_away_warnings,
                    "remaining": max(self._max_warnings - self._looked_away_warnings, 0),
                }
            )

        if self._looked_away_warnings >= self._max_warnings:
            await self.session.send_client_content(
                turns={
                    "role": "user",
                    "parts": [
                        {
                            "text": "--SYSTEM-- User looked away too much. Reject Them politely and end the call.",
                        }
                    ],
                },
                turn_complete=True,
            )
            await self.websocket.send_json(
                {
                    "type": "monitor",
                    "event": "look_away_terminated",
                    "warnings": self._looked_away_warnings,
                }
            )
            await self._finalize_session("look_away_limit")
            return

    async def _forward_model_responses(self) -> None:
        assert self.session is not None
        while True:
            if self._shutdown_reason:
                return
            turn = self.session.receive()
            async for response in turn:
                server_content = getattr(response, "server_content", None)
                assistant_text: Optional[str] = None

                if server_content and server_content.input_transcription:
                    payload = server_content.input_transcription.model_dump()
                    self._record_transcript("user", payload)
                    await self.websocket.send_json(
                        {
                            "type": "transcript",
                            "role": "user",
                            "payload": payload,
                        }
                    )
                if server_content and server_content.output_transcription:
                    payload = server_content.output_transcription.model_dump()
                    self._record_transcript("assistant", payload)
                    assistant_text = self._extract_transcript_text(payload)
                    await self.websocket.send_json(
                        {
                            "type": "transcript",
                            "role": "assistant",
                            "payload": payload,
                        }
                    )
                if data := response.data:
                    async with self._audio_lock:
                        self._assistant_chunks.extend(data)
                    encoded = base64.b64encode(data).decode("ascii")
                    await self.websocket.send_json(
                        {
                            "type": "audio",
                            "data": encoded,
                            "sampleRate": RECEIVE_SAMPLE_RATE,
                        }
                    )
                    continue
                text = response.text
                if text:
                    await self.websocket.send_json({"type": "text", "text": text})
                update = getattr(response, "session_resumption_update", None)
                if update and getattr(update, "resumable", False) and getattr(update, "new_handle", None):
                    new_handle = update.new_handle
                    if new_handle != self._resume_handle:
                        self._resume_handle = new_handle
                        await self.websocket.send_json(
                            {
                                "type": "session_resumption",
                                "handle": new_handle,
                            }
                        )
                        logger.info("Session can be resumed with handle: %s", new_handle)

                if await self._maybe_finalize_from_response(
                    server_content=server_content,
                    assistant_text=assistant_text,
                    message_text=text,
                ):
                    return

    def _record_transcript(self, role: str, payload: Dict[str, Any]) -> None:
        timestamp = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        entry: Dict[str, Any] = {
            "timestamp": timestamp,
            "role": role,
            "payload": payload,
        }
        text = payload.get("transcript") or payload.get("text")
        if text:
            entry["text"] = text
        self._transcripts.append(entry)

    def _extract_transcript_text(self, payload: Dict[str, Any]) -> Optional[str]:
        if not payload:
            return None
        if isinstance(payload.get("transcript"), str):
            return payload["transcript"].strip()
        if isinstance(payload.get("text"), str):
            return payload["text"].strip()

        segments = payload.get("segments")
        if isinstance(segments, list):
            parts = []
            for segment in segments:
                if isinstance(segment, dict):
                    text_value = segment.get("text")
                    if isinstance(text_value, str):
                        parts.append(text_value)
            if parts:
                return " ".join(parts).strip()

        alternatives = payload.get("alternatives")
        if isinstance(alternatives, list):
            for alternative in alternatives:
                if isinstance(alternative, dict):
                    text_value = alternative.get("text")
                    if isinstance(text_value, str):
                        return text_value.strip()
        return None

    async def _maybe_finalize_from_response(
        self,
        *,
        server_content: Optional[genai_types.LiveServerContent],
        assistant_text: Optional[str],
        message_text: Optional[str],
    ) -> bool:
        if self._shutdown_reason:
            return True

        combined = " ".join(
            value.strip() for value in (assistant_text, message_text) if value
        ).lower()

        if combined:
            for phrase in FINAL_SIGNOFF_PHRASES:
                if phrase in combined:
                    await self._finalize_session(
                        "assistant_signoff",
                        detail=assistant_text or message_text or phrase,
                    )
                    return True

        if server_content:
            reason = server_content.turn_complete_reason
            if reason and reason not in (
                genai_types.TurnCompleteReason.NEED_MORE_INPUT,
                genai_types.TurnCompleteReason.TURN_COMPLETE_REASON_UNSPECIFIED,
            ):
                await self._finalize_session(reason.value.lower())
                return True

        return False

    async def _finalize_session(
        self,
        reason: str,
        *,
        detail: Optional[str] = None,
    ) -> bool:
        if self._shutdown_reason:
            return False

        self._shutdown_reason = reason
        self._session_terminated = True
        self._resume_handle = None

        if self.session is not None:
            try:
                await self.session.send_realtime_input(audio_stream_end=True)
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Failed to signal audio_stream_end: %s", exc)

        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.send_json(
                {
                    "type": "session_complete",
                    "reason": reason,
                    "detail": detail,
                }
            )

        logger.info(
            "Session %s flagged for shutdown: %s",
            self._session_id,
            reason,
        )

        return True

    async def _safe_close(self) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.close()

    def _write_wav(self, path: Path, pcm: bytes, sample_rate: int) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)

    def _mix_wavs(self, assistant_path: Path, candidate_path: Path, mix_path: Path) -> None:
        try:
            with wave.open(str(assistant_path), "rb") as assistant_wav, wave.open(
                str(candidate_path), "rb"
            ) as candidate_wav:
                if (
                    assistant_wav.getnchannels() != 1
                    or candidate_wav.getnchannels() != 1
                    or assistant_wav.getsampwidth() != 2
                    or candidate_wav.getsampwidth() != 2
                ):
                    return

                assistant_frames = assistant_wav.readframes(assistant_wav.getnframes())
                candidate_frames = candidate_wav.readframes(candidate_wav.getnframes())

                min_len = min(len(assistant_frames), len(candidate_frames))
                if min_len == 0:
                    return

                import array

                assistant_array = array.array("h", assistant_frames[:min_len])
                candidate_array = array.array("h", candidate_frames[:min_len])

                mix_array = array.array("h")
                for a, b in zip(assistant_array, candidate_array):
                    mixed = int((int(a) + int(b)) / 2)
                    mix_array.append(max(-32768, min(32767, mixed)))

                with wave.open(str(mix_path), "wb") as mix_wav:
                    mix_wav.setnchannels(1)
                    mix_wav.setsampwidth(2)
                    mix_wav.setframerate(assistant_wav.getframerate())
                    mix_wav.writeframes(mix_array.tobytes())
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to mix wav files: %s", exc)

    def _write_transcripts(self, path: Path, transcripts: List[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as outfile:
            for entry in transcripts:
                outfile.write(json.dumps(entry, ensure_ascii=False))
                outfile.write("\n")
        
        # Create formatted Transcript and Score Candidate
        self._format_transcript_and_score(path, transcripts)
    
    def _format_transcript_and_score(self, path: Path, transcripts: List[Dict[str, Any]]) -> None:
        formatted_path = path.parent / f"{self._session_prefix}_formatted_transcript.txt"
        score_path = path.parent / f"{self._session_prefix}_score.txt"

        formatted_path.parent.mkdir(parents=True, exist_ok=True)

        lines: List[str] = []
        current_role: Optional[str] = None
        current_timestamp: Optional[str] = None
        current_parts: List[str] = []

        def flush_current() -> None:
            if current_role and current_parts:
                combined = "".join(current_parts).strip()
                if combined:
                    lines.append(f"[{current_timestamp}] {current_role.upper()}: {combined}")

        for entry in transcripts:
            role = entry.get("role")
            if not role:
                continue
            text = entry.get("text") or ""
            if not text.strip():
                continue

            timestamp = entry.get("timestamp") or current_timestamp
            payload = entry.get("payload") or {}
            finished = payload.get("finished")

            if role != current_role:
                flush_current()
                current_role = role
                current_timestamp = timestamp
                current_parts = [text]
            else:
                current_parts.append(text)

            if finished is True:
                flush_current()
                current_role = None
                current_timestamp = None
                current_parts = []

        flush_current()

        formatted_text = "\n".join(lines)
        formatted_path.write_text(formatted_text, encoding="utf-8")
        logger.info("Formatted transcript written to %s", formatted_path)

        if not formatted_text.strip():
            logger.info("Formatted transcript empty; skipping scoring for session %s", self._session_id)
            return

        try:
            resume_text = (BASE_DIR / "himanshu-resume.txt").read_text(encoding="utf-8")
            jd_text = (BASE_DIR / "SDE_JD.txt").read_text(encoding="utf-8")
            prompt_context = """
Score the candidate based on the following criteria:
1. Technical Skills: Evaluate the candidate's proficiency in relevant technical skills and knowledge.
2. Problem-Solving Ability: Assess the candidate's ability to analyze and solve problems effectively.
3. Communication Skills: Rate the candidate's ability to communicate ideas clearly and effectively.
4. Cultural Fit: Determine how well the candidate aligns with the company's values and culture.
5. Overall Impression: Provide an overall score based on the candidate's performance during the interview.

Give reasons and key takeaways for each criteria. Provide separate scores (out of 10) for resume match and interview performance, then give a final averaged score out of 10.
"""

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents={
                    "role": "user",
                    "parts": [
                        genai_types.Part.from_text(text=formatted_text),
                        genai_types.Part.from_text(text=resume_text),
                        genai_types.Part.from_text(text=jd_text),
                        genai_types.Part.from_text(text=prompt_context),
                    ],
                },
            )

            score_path.write_text(response.text or "", encoding="utf-8")
            logger.info("Final evaluation written to %s", score_path)
        except Exception as exc:  
            logger.warning("Failed to generate candidate score: %s", exc)
            logger.info(traceback.format_exc())


@app.websocket("/ws/interview")
async def interview_endpoint(websocket: WebSocket) -> None:
    resume_handle = websocket.query_params.get("resume")
    handler = WebSocketInterviewSession(websocket, resume_handle=resume_handle)
    try:
        await handler.run()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error in interview session", exc_info=exc)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011)


@app.exception_handler(Exception)
async def global_exception_handler(_, exc: Exception):  # pylint: disable=broad-except
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
