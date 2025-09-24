"""
## Documentation
Quickstart: https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py

## Setup

To install the dependencies for this script, run:

```
pip install google-genai opencv-python pyaudio pillow mss
# Optional for MP3 export
pip install pydub
```
Note: For MP3 export you also need FFmpeg installed and on PATH.
Windows: download from https://ffmpeg.org/download.html and add the bin folder to PATH.
ref:
https://www.tutorialspoint.com/how-to-detect-eyes-in-an-image-using-opencv-python
"""

import os
import json
import asyncio
import base64
import io
import traceback
import pathlib
import time
import wave
import subprocess
import shutil
from datetime import datetime

import cv2
import pyaudio
import PIL.Image
import mss

import argparse

from google import genai
from google.genai import types

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# MODEL = "models/gemini-2.5-flash-preview-native-audio-dialog"
MODEL = "models/gemini-2.5-flash-live-preview"

DEFAULT_MODE = "camera"

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=os.environ.get("GEMINI_API_KEY", "<Enter your API key here>"),
)

face_cascade = cv2.CascadeClassifier('haarcascades\\haarcascade_frontalface_default.xml')

# read the haarcascade to detect the eyes in an image
eye_cascade = cv2.CascadeClassifier('haarcascades\\haarcascade_eye_tree_eyeglasses.xml')

with open("ADS_moksh_resume.txt", "r", encoding="utf-8") as f:
    resume = f.read()
with open("ADS_JD.txt", "r", encoding="utf-8") as f:
    jd = f.read()

CONFIG = types.LiveConnectConfig(
    system_instruction=f"""
    You are ALEX. YOU HAVE A VERY IMPORTANT JOB OF Conducting Interviews for the provided Job Description.

YOU ARE ON CALL WITH INTERVIEWEE MENTIONED IN THE RESUME

YOUR AIM IS TO CONDUCT AN ENGAGING INTERVIEW TO ASSESS INTERVIEWW IN THE APPROPRIATE SKILLS.

BE POLITE AND FRIENDLY. DO NOT BE RUDE OR IMPOLITE. GUIDE HIMANSHU IF HE GETS STUCK BUT BE CAREFUL NOT TO GIVE AWAY TOO MUCH INFORMATION.
DO NOT INTERRUPT HIM WHEN HE IS SPEAKING.
AVOID USING COMPLEX JARGON OR TECHNICAL TERMS THAT HE MAY NOT UNDERSTAND.
DO NOT STRAY FROM THE INTERVIEW QUESTIONS

PLEASE SPEAK IN ENGLISH LANGUAGE IN AMERICAN ACCENT

WHEN THE INTERVIEW IS OVER OR REJECTED SAY "I hope you have a great day!"

JOB DESCRIPTION: ```{jd}```
RESUME: ```{resume}```
""",
    response_modalities=[
        "AUDIO",
    ],
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
        )
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
    input_audio_transcription={},
    output_audio_transcription={}
)

pya = pyaudio.PyAudio()


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE):
        self.video_mode = video_mode

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None
        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None
        self.looked_away = 0
        self.looked_away_warnings = 0

        # Buffers to record audio during the live session
        self._assistant_bytes = bytearray()  # model's audio (what we play)
        self._mic_bytes = bytearray()        # user's mic audio (what we send)
        self._assistant_lock = asyncio.Lock()
        self._mic_lock = asyncio.Lock()
        self._recordings_dir = pathlib.Path("recordings")
        self._recordings_dir.mkdir(exist_ok=True)

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            await self.session.send_client_content(
                turns={
                    "role": "user",
                    "parts": [{
                        "text": text or "."
                    }]
                },
                turn_complete=True
            )

    def _get_frame(self, cap):
        # Read the frameq
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")

        faces = face_cascade.detectMultiScale(gray, 1.3, 4)
        eyes = eye_cascade.detectMultiScale(gray, 1.3, 4)
        print('Number of detected eyes:', len(eyes))
        if len(faces) >= 1:
            self.looked_away = 0
        if len(faces) < 1:
            self.looked_away += 1
        # print('Number of detected faces:', len(faces), 'Looked away count:', self.looked_away)
        cv2.imshow("frame", frame)


        if cv2.waitKey(1) & 0xFF == ord("q"):
            cv2.destroyAllWindows()
            return None
        # img.show()
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        # This takes about a second, and will block the whole program
        # causing the audio pipeline to overflow if you don't to_thread it.
        cap = await asyncio.to_thread(
            cv2.VideoCapture, 0
        )  # 0 represents the default camera

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            # await asyncio.sleep(1.0)
            await asyncio.sleep(0.2)

            if self.looked_away > 10:
                self.looked_away_warnings += 1
                await self.session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{
                            "text": f"--SYSTEM-- User looking away - warn the candidate it's the {self.looked_away_warnings} time(s) and {3 - self.looked_away_warnings} warning(s) left."
                        }]
                    },
                    turn_complete=True
                )
                self.looked_away = 0
            if self.looked_away_warnings == 3:
                await self.session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{
                            "text": f"--SYSTEM-- User looked away too much. Reject Them politely and end the call."
                        }]
                    },
                    turn_complete=True
                )

            await self.out_queue.put(frame)

        # Release the VideoCapture object
        cap.release()
        cv2.destroyAllWindows()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):

        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            # await self.session.send(input=msg)
            await self.session.send_realtime_input(media=msg)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            # Create a pcm file and write the data
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
            # Record mic audio
            async with self._mic_lock:
                self._mic_bytes.extend(data)

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if response.server_content.input_transcription:
                    with open("transcriptions.txt", "a", encoding="utf-8") as f:
                        f.write(f"INPUT: {response.server_content.input_transcription.model_dump_json()}\n")
                if response.server_content.output_transcription:
                    with open("transcriptions.txt", "a", encoding="utf-8") as f:
                        f.write(f"OUTPUT: {response.server_content.output_transcription.model_dump_json()}\n")

                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    # Record assistant audio
                    async with self._assistant_lock:
                        self._assistant_bytes.extend(data)
                    continue
                if text := response.text:
                    print(text, end="")

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            async with (
                client.aio.live.connect(
                    model=MODEL, 
                    config=CONFIG
                ) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                await self.session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{
                            "text": f"--SYSTEM-- Candidate Joined the call."
                        }]
                    },
                    turn_complete=True
                )
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            self.audio_stream.close()
            traceback.print_exception(EG)
        finally:
            # On exit, persist recordings to disk and try to produce final MP3(s)
            try:
                await self._finalize_recordings()
            except Exception:
                traceback.print_exc()
            # Ensure audio stream is closed
            try:
                if hasattr(self, 'audio_stream') and self.audio_stream:
                    self.audio_stream.close()
            except Exception:
                pass

    def _write_wav(self, wav_path: pathlib.Path, pcm_bytes: bytes, sample_rate: int):
        # Write PCM 16-bit mono data to WAV container
        with wave.open(str(wav_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)

    def _ffmpeg_available(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def _convert_wav_to_mp3(self, wav_path: pathlib.Path, mp3_path: pathlib.Path) -> bool:
        # Try pydub first (if available and ffmpeg configured), else fallback to ffmpeg CLI
        try:
            from pydub import AudioSegment  # type: ignore
            audio = AudioSegment.from_wav(str(wav_path))
            audio.export(str(mp3_path), format="mp3", bitrate="128k")
            return True
        except Exception:
            # Fallback to CLI ffmpeg if present
            if self._ffmpeg_available():
                try:
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(wav_path),
                        "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3_path)
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    return False
            return False

    async def _finalize_recordings(self):
        print("\nFinalizing recordings...")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Assistant audio (what we played back)
        assistant_wav = self._recordings_dir / f"session_assistant_{ts}.wav"
        assistant_mp3 = self._recordings_dir / f"session_assistant_{ts}.mp3"
        # Mic audio (what we sent)
        mic_wav = self._recordings_dir / f"session_mic_{ts}.wav"
        mic_mp3 = self._recordings_dir / f"session_mic_{ts}.mp3"
        # Mixed duo track (assistant + mic)
        mix_mp3 = self._recordings_dir / f"session_mix_{ts}.mp3"

        # Snapshot current buffers
        # Acquire locks asynchronously to avoid race conditions with any pending tasks
        try:
            async with self._assistant_lock:
                assistant_bytes = bytes(self._assistant_bytes)
        except Exception:
            assistant_bytes = bytes(self._assistant_bytes)
        try:
            async with self._mic_lock:
                mic_bytes = bytes(self._mic_bytes)
        except Exception:
            mic_bytes = bytes(self._mic_bytes)

        # Save WAVs (always succeeds without external deps)
        if assistant_bytes:
            self._write_wav(assistant_wav, assistant_bytes, RECEIVE_SAMPLE_RATE)
        if mic_bytes:
            self._write_wav(mic_wav, mic_bytes, SEND_SAMPLE_RATE)

        # Try to produce MP3(s)
        if assistant_bytes:
            if not self._convert_wav_to_mp3(assistant_wav, assistant_mp3):
                print(f"[warn] Could not create MP3 for assistant audio. WAV saved at: {assistant_wav}")
            else:
                print(f"[ok] Assistant MP3 saved: {assistant_mp3}")
        if mic_bytes:
            if not self._convert_wav_to_mp3(mic_wav, mic_mp3):
                print(f"[warn] Could not create MP3 for mic audio. WAV saved at: {mic_wav}")
            else:
                print(f"[ok] Mic MP3 saved: {mic_mp3}")

        # Try to produce a single mixed MP3 if both streams exist
        if assistant_bytes and mic_bytes:
            mixed_ok = False
            try:
                from pydub import AudioSegment  # type: ignore
                a = AudioSegment.from_wav(str(assistant_wav))
                m = AudioSegment.from_wav(str(mic_wav))
                # Slightly reduce each to avoid clipping when mixing
                a = a - 2
                m = m - 2
                mixed = a.overlay(m)
                mixed.export(str(mix_mp3), format="mp3", bitrate="128k")
                mixed_ok = True
            except Exception:
                # Fallback to ffmpeg amix
                if self._ffmpeg_available():
                    try:
                        subprocess.run([
                            "ffmpeg", "-y",
                            "-i", str(assistant_wav),
                            "-i", str(mic_wav),
                            "-filter_complex", "[0:a][1:a]amix=inputs=2:dropout_transition=2:normalize=0,volume=1.0[a]",
                            "-map", "[a]",
                            "-codec:a", "libmp3lame", "-b:a", "128k",
                            str(mix_mp3)
                        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        mixed_ok = True
                    except Exception:
                        mixed_ok = False
            if mixed_ok:
                print(f"[ok] Mixed MP3 saved: {mix_mp3}")
            else:
                print("[warn] Could not create mixed MP3; individual WAV/MP3 files were saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = AudioLoop(video_mode=args.mode)
    asyncio.run(main.run())
