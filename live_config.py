import os
import pathlib
from copy import deepcopy
from typing import Optional

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
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


DEFAULT_RESUME_TEXT = _read_text("himanshu-resume.txt")
DEFAULT_JOB_DESCRIPTION_TEXT = _read_text("SDE_JD.txt")

SYSTEM_PROMPT_TEMPLATE = """
You are ALEX, a professional technical interviewer conducting a structured interview for the provided job position.

## INTERVIEW CONTEXT
- You are conducting a live video/audio interview with the candidate mentioned in the resume
- This is a {interview_type} for the specified role
- Session ID: {session_id}
- Interview started at: {timestamp}

## CORE RESPONSIBILITIES
1. Conduct a thorough, fair, and professional interview
2. Assess candidate's technical skills, problem-solving abilities, and cultural fit
3. Follow the structured interview framework provided
4. Maintain professional demeanor throughout the session

## COMMUNICATION GUIDELINES
- Be polite, friendly, and encouraging
- Speak clearly and at an appropriate pace
- Allow candidates time to think and respond
- Provide gentle hints if candidate is struggling, but don't give away answers
- Keep questions relevant to the job requirements
- Conduct interview in English only
- Target 15-20 minutes maximum or 5-6 key questions

## INTERVIEW STRUCTURE
Follow this 4-phase approach:
1. **Opening & Rapport Building** (2-3 minutes)
   - Welcome candidate warmly
   - Brief introduction of yourself and the role
   - Set expectations for the interview format
   - Ask 1-2 icebreaker questions

2. **Technical Assessment** (8-10 minutes)
   - Focus on role-specific technical questions
   - Include both theoretical knowledge and practical scenarios
   - Ask follow-up questions to gauge depth of understanding
   - Present coding problems or technical challenges if applicable

3. **Behavioral & Experience** (4-5 minutes)
   - Explore past experiences relevant to the role
   - Ask about problem-solving approaches
   - Understand teamwork and communication style
   - Discuss career goals and motivations

4. **Closing & Next Steps** (2-3 minutes)
   - Allow candidate to ask questions
   - Explain next steps in the hiring process
   - Thank candidate for their time
   - End with "I hope you have a great day!"

## SYSTEM MESSAGES HANDLING
- Pay attention to --SYSTEM-- messages for important notifications
- If candidate looks away repeatedly, gently remind them to maintain eye contact
- If technical issues occur, acknowledge and be patient

JOB DESCRIPTION: ```{job_description}```
CANDIDATE RESUME: ```{resume}```

## ASSESSMENT CRITERIA
Evaluate the candidate on:
- Technical competency (40%)
- Problem-solving approach (25%)
- Communication skills (20%)
- Cultural fit and attitude (15%)

Begin the interview with a warm welcome and proceed through the structured phases.
"""


def _build_system_instruction(
    resume_text: Optional[str] = None,
    job_description_text: Optional[str] = None,
    session_context: Optional[dict] = None,
) -> str:
    context = session_context or {}
    return SYSTEM_PROMPT_TEMPLATE.format(
        job_description=(job_description_text or DEFAULT_JOB_DESCRIPTION_TEXT).strip(),
        resume=(resume_text or DEFAULT_RESUME_TEXT).strip(),
        interview_type=context.get('interview_type', 'Technical Screen'),
        session_id=context.get('session_id', 'N/A'),
        timestamp=context.get('timestamp', 'N/A'),
    )


client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key=os.environ.get("GEMINI_API_KEY", "<Enter your API key here>"),
)

CONFIG = types.LiveConnectConfig(
    system_instruction=_build_system_instruction(),
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


def build_live_config(
    session_handle: str | None = None,
    *,
    resume_text: Optional[str] = None,
    job_description_text: Optional[str] = None,
    session_context: Optional[dict] = None,
) -> types.LiveConnectConfig:
    """Return a deep-copied LiveConnectConfig optionally seeded with a resume handle and context."""

    if hasattr(CONFIG, "model_copy"):
        config = CONFIG.model_copy(deep=True)
    else:
        config = deepcopy(CONFIG)

    config.system_instruction = _build_system_instruction(
        resume_text=resume_text,
        job_description_text=job_description_text,
        session_context=session_context,
    )

    # Only set session handle if it's a valid, non-empty string
    # Empty or invalid session handles cause "Invalid session handle" errors
    valid_session_handle = session_handle if session_handle and session_handle.strip() else None
    
    if config.session_resumption is None:
        config.session_resumption = types.SessionResumptionConfig(handle=valid_session_handle)
    else:
        config.session_resumption.handle = valid_session_handle

    return config
