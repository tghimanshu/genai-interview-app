import asyncio
import base64
import json
import logging
import wave
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Response,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState
from pydantic import BaseModel
from utils.email_utils import send_email
from convert_resume_to_text import convert_resume_to_txt

import cv2
import numpy as np
from google.genai import types as genai_types

from live_config import (
    BASE_DIR,
    MODEL,
    RECEIVE_SAMPLE_RATE,
    SEND_SAMPLE_RATE,
    DEFAULT_JOB_DESCRIPTION_TEXT,
    DEFAULT_RESUME_TEXT,
    build_live_config,
    client,
)
from enhanced_ai_config import get_enhanced_ai_config

# WebRTC imports handled separately to avoid circular imports

# Setup logging first
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Import database operations
try:
    from database_operations import (
        InterviewDatabaseOps,
        JobDescription,
        Resume,
        Interview,
    )

    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logger.warning(
        "Database operations not available - database_operations.py not found"
    )


# Pydantic models for API requests
class JobDescriptionCreate(BaseModel):
    title: str
    company: str
    description_text: str
    requirements: Optional[str] = None
    skills_required: Optional[str] = None
    experience_level: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None


class ResumeCreate(BaseModel):
    candidate_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    resume_text: str
    skills: Optional[str] = None
    education: Optional[str] = None
    experience_years: Optional[int] = None


class InterviewCreate(BaseModel):
    job_description_id: int
    resume_id: int
    session_id: str
    duration_minutes: Optional[int] = None


FINAL_SIGNOFF_PHRASES = (
    "i hope you have a great day",
    "have a great day",
    "enjoy the rest of your day",
)

app = FastAPI(title="Live Interview API")

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

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


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
async def login(login_request: LoginRequest):
    """Simple hard-coded login for development/testing.
    Accepts JSON {"username": "...", "password": "..."} and returns a token
    when credentials match admin/admin.
    """
    try:
        username = login_request.username or ""
        password = login_request.password or ""
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid login payload")

    # Hard-coded credentials for now
    if username == "admin" and password == "admin":
        # In a real app you'd issue a signed JWT or similar. For now return a
        # simple token string that the frontend will store and include in requests.
        return {"token": "hardcoded-admin-token", "message": "Login successful"}

    raise HTTPException(status_code=401, detail="Invalid username or password")


# Database API Endpoints


# Job Descriptions
@app.get("/api/jobs")
async def get_job_descriptions(response: Response):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        jobs = db_ops.list_job_descriptions(active_only=True)

        # Add caching headers for better performance
        response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes

        return {"jobs": jobs}
    except Exception as e:
        logger.error(f"Error fetching job descriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/jobs")
async def create_job_description(job_data: JobDescriptionCreate):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        # Create JobDescription dataclass object
        job_desc = JobDescription(
            title=job_data.title,
            company=job_data.company,
            description_text=job_data.description_text,
            requirements=job_data.requirements,
            skills_required=job_data.skills_required,
            experience_level=job_data.experience_level,
            location=job_data.location,
            salary_range=job_data.salary_range,
        )
        job_id = db_ops.create_job_description(job_desc)
        return {"id": job_id, "message": "Job description created successfully"}
    except Exception as e:
        logger.error(f"Error creating job description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}")
async def get_job_description(job_id: int):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        job = db_ops.get_job_description(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job description not found")
        return job
    except Exception as e:
        logger.error(f"Error fetching job description {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Resumes/Candidates
@app.get("/api/resumes")
async def get_resumes(response: Response):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        resumes = db_ops.list_resumes(active_only=True)

        # Add caching headers for better performance
        response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes

        return {"resumes": resumes}
    except Exception as e:
        logger.error(f"Error fetching resumes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resumes")
async def create_resume(resume_data: ResumeCreate):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        # Create Resume dataclass object
        resume = Resume(
            candidate_name=resume_data.candidate_name,
            email=resume_data.email,
            phone=resume_data.phone,
            resume_text=resume_data.resume_text,
            skills=resume_data.skills,
            education=resume_data.education,
            experience_years=resume_data.experience_years,
        )
        resume_id = db_ops.create_resume(resume)
        return {"id": resume_id, "message": "Resume created successfully"}
    except Exception as e:
        logger.error(f"Error creating resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resumes/upload")
async def upload_resume(
    candidate_name: str = Form(...),
    email: Optional[str] = Form(None),
    resume_file: UploadFile = File(...),
):
    """Upload a resume file and create a resume record.
    - text files will be read into resume_text
    - other files (pdf, docx) will be stored and path saved in resume_pdf_path
    """
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Save uploaded file
        uploads_dir = Path(BASE_DIR) / "uploads" / "resumes"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # sanitize filename
        original_name = Path(resume_file.filename).name
        unique_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{original_name}"
        dest_path = uploads_dir / unique_name

        content = await resume_file.read()
        with open(dest_path, "wb") as f:
            f.write(content)

        # If text-like, decode into resume_text
        details = None
        # TODO: Convert Resume to text and create resume
        try:
            # if resume_file.content_type and resume_file.content_type.startswith("text"):
            #     resume_text = content.decode("utf-8", errors="ignore")
            details = convert_resume_to_txt(dest_path)
        except Exception as e:
            resume_text = None

        # Create resume record
        db_ops = InterviewDatabaseOps()
        if details:
            resume = Resume(
                candidate_name=details.get("candidate_name"),
                resume_text=details.get("resume_text", ""),
                email=details.get("email"),
                resume_pdf_path=str(dest_path),
                phone=details.get("phone"),
                skills=details.get("skills"),
                education=details.get("education"),
                experience_years=details.get("experience_years"),
                certifications=details.get("certifications"),
                linkedin_url=details.get("linkedin_url"),
                portfolio_url=details.get("portfolio_url"),
            )
        # resume = Resume(
        #     candidate_name=candidate_name,
        #     resume_text=resume_text or "",
        #     email=email,
        #     resume_pdf_path=str(dest_path),
        # )
        resume_id = db_ops.create_resume(resume)

        return {"id": resume_id, "message": "Resume uploaded and created successfully"}

    except Exception as e:
        logger.error(f"Error uploading resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/resumes/{resume_id}")
async def get_resume(resume_id: int):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        resume = db_ops.get_resume(resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        return resume
    except Exception as e:
        logger.error(f"Error fetching resume {resume_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Interviews
@app.get("/api/interviews")
async def get_interviews():
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        # Get all interviews
        interviews = db_ops.list_interviews(limit=50)
        return {"interviews": interviews}
    except Exception as e:
        logger.error(f"Error fetching interviews: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interviews")
async def create_interview(interview_data: InterviewCreate):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        # Create Interview dataclass object
        interview = Interview(
            job_description_id=interview_data.job_description_id,
            resume_id=interview_data.resume_id,
            session_id=interview_data.session_id,
            duration_minutes=interview_data.duration_minutes,
            interview_link=f"http://localhost:5173/interview/{interview_data.session_id}",
            status="scheduled",  # Set default status
        )
        resume = db_ops.get_resume(interview_data.resume_id)  # Verify resume exists
        interview_id = db_ops.create_interview(interview)
        if interview_id:
            send_email(
                recipients=[resume.get("email")],
                subject="Interview Scheduled",
                body=f"Your interview has been scheduled successfully. Join here: {interview.interview_link}",
            )
        return {"id": interview_id, "message": "Interview created successfully"}
    except Exception as e:
        logger.error(f"Error creating interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/interviews/{interview_id}")
async def get_interview_details(interview_id: int):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        interview_details = db_ops.get_interview_full_results(interview_id)
        if not interview_details:
            raise HTTPException(status_code=404, detail="Interview not found")
        return interview_details
    except Exception as e:
        logger.error(f"Error fetching interview details {interview_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/interviews/{interview_id}/results")
async def get_interview_results(interview_id: int):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        interview_summary = db_ops.get_interview_summary(interview_id)
        if not interview_summary:
            raise HTTPException(status_code=404, detail="Interview not found")
        return interview_summary
    except Exception as e:
        logger.error(f"Error fetching interview results {interview_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics
@app.get("/api/analytics/stats")
async def get_analytics_stats():
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        # Get basic counts using existing methods
        all_jobs = db_ops.list_job_descriptions(active_only=False)
        all_resumes = db_ops.list_resumes(active_only=False)
        all_interviews = db_ops.list_interviews()  # Get all interviews
        all_scores = db_ops.get_all_interview_results()["final_score"]

        # Calculate stats
        total_jobs = len(all_jobs)
        total_candidates = len(all_resumes)
        total_interviews = len(all_interviews)

        # Simple average score calculation
        # avg_score = 7.5  # Default placeholder
        avg_score = (
            sum(score["final_score"] for score in all_scores) / len(all_scores)
            if all_scores
            else 0
        )

        return {
            "totalJobs": total_jobs,
            "totalCandidates": total_candidates,
            "totalInterviews": total_interviews,
            "averageScore": avg_score,
        }
    except Exception as e:
        logger.error(f"Error fetching analytics stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# UPDATE endpoints
@app.put("/api/jobs/{job_id}")
async def update_job_description(job_id: int, job_data: JobDescriptionCreate):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        # Convert Pydantic model to dict for update
        updates = job_data.model_dump(exclude_none=True)

        success = db_ops.update_job_description(job_id, updates)
        if not success:
            raise HTTPException(status_code=404, detail="Job description not found")

        # Return updated job
        updated_job = db_ops.get_job_description(job_id)
        return {"job": updated_job}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/resumes/{resume_id}")
async def update_resume(resume_id: int, resume_data: ResumeCreate):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        # Convert Pydantic model to dict for update
        updates = resume_data.model_dump(exclude_none=True)

        # Update resume in database (need to implement update_resume method)
        query = """
        UPDATE resumes 
        SET candidate_name = ?, email = ?, phone = ?, resume_text = ?,
            skills = ?, experience_years = ?, education = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """

        params = (
            updates.get("candidate_name"),
            updates.get("email"),
            updates.get("phone"),
            updates.get("resume_text"),
            updates.get("skills"),
            updates.get("experience_years"),
            updates.get("education"),
            resume_id,
        )

        success = db_ops.db_manager.execute_update(query, params)
        if not success:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Return updated resume
        updated_resume = db_ops.get_resume(resume_id)
        return {"resume": updated_resume}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/interviews/{interview_id}/status")
async def update_interview_status(interview_id: int, status_data: dict):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        status = status_data.get("status")
        if not status:
            raise HTTPException(status_code=400, detail="Status is required")

        success = db_ops.update_interview_status(interview_id, status)
        if not success:
            raise HTTPException(status_code=404, detail="Interview not found")

        # Return updated interview
        updated_interview = db_ops.get_interview(interview_id)

        # If interview completed, attempt to send notification email
        try:
            if status == "completed":
                # Fetch resume email if available
                resume = (
                    db_ops.get_resume(updated_interview["resume_id"])
                    if updated_interview
                    else None
                )
                candidate_email = resume.get("email") if resume else None
                session = (
                    updated_interview.get("session_id") if updated_interview else None
                )
                if candidate_email and session:
                    interview_link = (
                        f"{"http://localhost:5173"}/interview?session={session}"
                    )
                    subject = "Your Interview has completed"
                    body = f"Your interview session ({session}) is completed. Access details: {interview_link}"
                    send_email(subject, body, [candidate_email])
        except Exception as e:
            logger.error(f"Failed to send completion email: {e}")
        return {"interview": updated_interview}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating interview status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/interviews/{interview_id}")
async def update_interview(interview_id: int, updates: dict):
    """Update arbitrary interview fields (scheduled_at, duration_minutes, interviewer_notes, etc.)"""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        # Validate allowed keys to prevent accidental schema changes
        allowed_keys = {
            "scheduled_at",
            "started_at",
            "ended_at",
            "duration_minutes",
            "interviewer_notes",
            "candidate_feedback",
            "status",
        }

        filtered_updates = {k: v for k, v in updates.items() if k in allowed_keys}
        if not filtered_updates:
            raise HTTPException(
                status_code=400, detail="No valid update fields provided"
            )

        success = db_ops.update_interview(interview_id, filtered_updates)
        if not success:
            raise HTTPException(
                status_code=404, detail="Interview not found or update failed"
            )

        updated = db_ops.get_interview(interview_id)
        return {"interview": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# DELETE endpoints
@app.delete("/api/jobs/{job_id}")
async def delete_job_description(job_id: int):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        # Soft delete by setting is_active = False
        success = db_ops.update_job_description(job_id, {"is_active": False})
        if not success:
            raise HTTPException(status_code=404, detail="Job description not found")

        return {"message": "Job description deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/resumes/{resume_id}")
async def delete_resume(resume_id: int):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        # Soft delete by setting is_active = False to avoid violating FK constraints
        query = "UPDATE resumes SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        success = db_ops.db_manager.execute_update(query, (resume_id,))
        if not success:
            raise HTTPException(status_code=404, detail="Resume not found")

        return {"message": "Resume deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# SEARCH endpoints
@app.get("/api/search/candidates")
async def search_candidates(q: str):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        candidates = db_ops.search_candidates(q)
        return {"candidates": candidates}

    except Exception as e:
        logger.error(f"Error searching candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/jobs")
async def search_jobs(q: str):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        # Search jobs by title or company
        query = """
        SELECT * FROM job_descriptions 
        WHERE (title LIKE ? OR company LIKE ?) AND is_active = 1
        ORDER BY title
        """

        term = f"%{q}%"
        rows = db_ops.db_manager.execute_query(query, (term, term))
        jobs = [dict(row) for row in rows] if rows else []

        return {"jobs": jobs}

    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# MATCH RATING endpoints
@app.post("/api/match-rating")
async def create_match_rating(rating_data: dict):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()

        job_id = rating_data.get("job_description_id")
        resume_id = rating_data.get("resume_id")
        score = rating_data.get("overall_score")
        reasoning = rating_data.get("reasoning", "")

        if not all([job_id, resume_id, score]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        rating_id = db_ops.create_match_rating(
            job_id,
            resume_id,
            score,
            reasoning,
            rating_data.get("detailed_analysis"),
            rating_data.get("model_version"),
        )

        if not rating_id:
            raise HTTPException(status_code=500, detail="Failed to create match rating")

        return {"match_rating_id": rating_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating match rating: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/match-rating/{job_id}/{resume_id}")
async def get_match_rating(job_id: int, resume_id: int):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_ops = InterviewDatabaseOps()
        rating = db_ops.get_match_rating(job_id, resume_id)

        if not rating:
            raise HTTPException(status_code=404, detail="Match rating not found")

        return {"match_rating": rating}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting match rating: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class WebSocketInterviewSession:
    def __init__(
        self, websocket: WebSocket, resume_handle: Optional[str] = None
    ) -> None:
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
        self._resume_text: str = DEFAULT_RESUME_TEXT
        self._job_description_text: str = DEFAULT_JOB_DESCRIPTION_TEXT
        self._shutdown_reason: Optional[str] = None
        self._interview_context: Dict[str, Any] = {}
        self._look_away_warnings_sent = 0

    async def run(self) -> None:
        await self.websocket.accept()
        try:
            # Build enhanced AI configuration
            session_context = {
                "session_id": self._session_id,
                "interview_type": "Technical Screen",
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Use enhanced config from enhanced_ai_config.py if available
            try:
                # Get context from web socket with type 'context' message
                while True:
                    message = await self.websocket.receive_json()
                    if message.get("type") == "context":
                        # session_context.update(message.get("context", {}))
                        enhanced_prompt = get_enhanced_ai_config(
                            message.get(
                                "jobDescriptionText", self._job_description_text
                            ),
                            message.get("resumeText", self._resume_text),
                            # self._job_description_text,
                            # self._resume_text,
                            session_context,
                        )
                        break

                config = build_live_config(
                    self._resume_handle,
                    resume_text=self._resume_text,
                    job_description_text=self._job_description_text,
                    session_context=session_context,
                )
                # Override with enhanced system instruction
                config.system_instruction = enhanced_prompt

            except ImportError:
                # Fallback to standard config with session context
                config = build_live_config(
                    self._resume_handle,
                    resume_text=self._resume_text,
                    job_description_text=self._job_description_text,
                    session_context=session_context,
                )

            try:
                async with client.aio.live.connect(
                    model=MODEL, config=config
                ) as session:
                    self.session = session
                    logger.info(
                        f"Successfully connected to Gemini Live API for session {self._session_id}"
                    )

                    await session.send_client_content(
                        turns={
                            "role": "user",
                            "parts": [
                                {"text": "--SYSTEM-- Candidate Joined the call."}
                            ],
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

            except Exception as api_error:
                logger.error(f"Error connecting to Gemini Live API: {api_error}")

                # Send error message to client
                if self.websocket.client_state == WebSocketState.CONNECTED:
                    await self.websocket.send_json(
                        {
                            "type": "error",
                            "error": "Failed to connect to AI service. Please try again.",
                            "details": str(api_error),
                        }
                    )

                # If it's a session handle error, suggest starting fresh
                if "Invalid session handle" in str(api_error):
                    logger.warning(
                        "Invalid session handle detected, client should start new session"
                    )
                    if self.websocket.client_state == WebSocketState.CONNECTED:
                        await self.websocket.send_json(
                            {
                                "type": "session_expired",
                                "message": "Session expired. Please start a new interview.",
                            }
                        )

                raise api_error
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
        transcripts_path = (
            self._recordings_dir / f"{self._session_prefix}_transcripts.jsonl"
        )

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
                    "mixPath": (
                        str(mix_path) if assistant_pcm and candidate_pcm else None
                    ),
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
                    logger.warning(
                        "Invalid JSON message from client: %s", message["text"]
                    )
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
            elif msg_type == "context":
                await self._handle_context_update(
                    resume_text=payload.get("resumeText"),
                    job_description_text=payload.get("jobDescriptionText"),
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
                    "remaining": max(
                        self._max_warnings - self._looked_away_warnings, 0
                    ),
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
                if (
                    update
                    and getattr(update, "resumable", False)
                    and getattr(update, "new_handle", None)
                ):
                    new_handle = update.new_handle
                    if new_handle != self._resume_handle:
                        self._resume_handle = new_handle
                        await self.websocket.send_json(
                            {
                                "type": "session_resumption",
                                "handle": new_handle,
                            }
                        )
                        logger.info(
                            "Session can be resumed with handle: %s", new_handle
                        )

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
            # if not task.done():
            #     task.cancel()
            if task.done():
                task.cancel()
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.close()

    def _write_wav(self, path: Path, pcm: bytes, sample_rate: int) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)

    def _mix_wavs(
        self, assistant_path: Path, candidate_path: Path, mix_path: Path
    ) -> None:
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

    def _format_transcript_and_score(
        self, path: Path, transcripts: List[Dict[str, Any]]
    ) -> None:
        formatted_path = (
            path.parent / f"{self._session_prefix}_formatted_transcript.txt"
        )
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
                    lines.append(
                        f"[{current_timestamp}] {current_role.upper()}: {combined}"
                    )

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
            logger.info(
                "Formatted transcript empty; skipping scoring for session %s",
                self._session_id,
            )
            return

        try:
            resume_text = (self._resume_text or DEFAULT_RESUME_TEXT).strip()
            jd_text = (
                self._job_description_text or DEFAULT_JOB_DESCRIPTION_TEXT
            ).strip()
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
                model="gemini-2.5-flash",
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

    async def _handle_context_update(
        self,
        *,
        resume_text: Optional[str],
        job_description_text: Optional[str],
    ) -> None:
        updated_fields: List[str] = []

        if isinstance(resume_text, str):
            normalized_resume = resume_text.strip()
            if normalized_resume:
                self._resume_text = normalized_resume
                updated_fields.append("resume")

        if isinstance(job_description_text, str):
            normalized_jd = job_description_text.strip()
            if normalized_jd:
                self._job_description_text = normalized_jd
                updated_fields.append("jobDescription")

        if not updated_fields:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(
                    {
                        "type": "context_ack",
                        "updated": [],
                    }
                )
            return

        if self.session is not None:
            try:
                await self.session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    "--SYSTEM-- Interview context updated. Use the following details for the remainder of this session.\n"
                                    f"JOB DESCRIPTION: ```{self._job_description_text}```\n"
                                    f"RESUME: ```{self._resume_text}```"
                                )
                            }
                        ],
                    },
                    turn_complete=True,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to push updated context to model: %s", exc)

        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.send_json(
                {
                    "type": "context_ack",
                    "updated": updated_fields,
                }
            )


@app.websocket("/ws/interview")
async def interview_endpoint(websocket: WebSocket) -> None:
    resume_handle = websocket.query_params.get("resume")

    # Validate and sanitize the resume handle
    # Only pass valid, non-empty session handles to avoid "Invalid session handle" errors
    validated_resume_handle = None
    if resume_handle and isinstance(resume_handle, str) and resume_handle.strip():
        validated_resume_handle = resume_handle.strip()
        logger.info(f"Using session resume handle: {validated_resume_handle}")
    else:
        logger.info("Starting new session (no valid resume handle provided)")

    handler = WebSocketInterviewSession(
        websocket, resume_handle=validated_resume_handle
    )
    try:
        await handler.run()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error in interview session", exc_info=exc)
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1011)
        except Exception as close_exc:  # pylint: disable=broad-except
            logger.exception("Error closing WebSocket connection", exc_info=close_exc)


@app.websocket("/ws/webrtc")
async def webrtc_endpoint(websocket: WebSocket) -> None:
    """WebRTC signaling endpoint for better audio/video performance"""
    await websocket.accept()
    session_id = None

    try:
        # Import webrtc_server functions here to avoid circular imports
        from webrtc_server import handle_webrtc_message, cleanup_session

        while True:
            # Receive signaling messages
            data = await websocket.receive_text()
            message = json.loads(data)

            # Track session ID for cleanup
            if not session_id and "session_id" in message:
                session_id = message["session_id"]
                logger.info(f"WebRTC session started: {session_id}")

            # Handle WebRTC signaling
            await handle_webrtc_message(websocket, message)

    except WebSocketDisconnect:
        logger.info(f"WebRTC client disconnected: {session_id}")
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error in WebRTC session", exc_info=exc)
    finally:
        if session_id:
            await cleanup_session(session_id)


@app.exception_handler(Exception)
async def global_exception_handler(_, exc: Exception):  # pylint: disable=broad-except
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
