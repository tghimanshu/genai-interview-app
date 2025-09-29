import os
import pathlib
from copy import deepcopy

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

BASE_DIR = pathlib.Path(__file__).resolve().parent

SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000

MODEL = "models/gemini-2.5-flash-live-preview"


def _read_text(filename: str) -> str:
    path = BASE_DIR / filename
    return path.read_text(encoding="utf-8")


RESUME_TEXT = _read_text("himanshu-resume.txt")
JOB_DESCRIPTION_TEXT = _read_text("SDE_JD.txt")

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=os.environ.get("GEMINI_API_KEY", "<Enter your API key here>"),
)

CONFIG = types.LiveConnectConfig(
    system_instruction=f"""
    You are ALEX. YOU HAVE A VERY IMPORTANT JOB OF Conducting Interviews for the provided Job Description.

YOU ARE ON CALL WITH INTERVIEWEE MENTIONED IN THE RESUME

YOUR AIM IS TO CONDUCT AN ENGAGING INTERVIEW TO ASSESS INTERVIEWW IN THE APPROPRIATE SKILLS.

BE POLITE AND FRIENDLY. DO NOT BE RUDE OR IMPOLITE. GUIDE HIMANSHU IF HE GETS STUCK BUT BE CAREFUL NOT TO GIVE AWAY TOO MUCH INFORMATION.
DO NOT INTERRUPT HIM WHEN HE IS SPEAKING.
AVOID USING COMPLEX JARGON OR TECHNICAL TERMS THAT HE MAY NOT UNDERSTAND.
DO NOT STRAY FROM THE INTERVIEW QUESTIONS

ENSURE THE CONVERSATION IS IN ENGLISH LANGUAGE ONLY
ENSURE THE INTERVIEW IS 15 MINUTES LONG ONLY OR 4 QUESTIONS MAXIMUM

WHEN THE INTERVIEW IS OVER OR REJECTED SAY "I hope you have a great day!"

JOB DESCRIPTION: ```{JOB_DESCRIPTION_TEXT}```
RESUME: ```{RESUME_TEXT}```
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
    output_audio_transcription={},
    session_resumption=types.SessionResumptionConfig(handle=None),
)


def build_live_config(session_handle: str | None = None) -> types.LiveConnectConfig:
    """Return a deep-copied LiveConnectConfig optionally seeded with a resume handle."""

    if hasattr(CONFIG, "model_copy"):
        config = CONFIG.model_copy(deep=True)
    else:
        config = deepcopy(CONFIG)

    if config.session_resumption is None:
        config.session_resumption = types.SessionResumptionConfig(handle=session_handle)
    else:
        config.session_resumption.handle = session_handle

    return config
