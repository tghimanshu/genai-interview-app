#!/usr/bin/env python3
"""
Database operations module for Live Interview App
Provides CRUD operations and business logic for all database entities
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging
from dataclasses import dataclass
from init_database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class JobDescription:
    """Data class for job descriptions"""

    title: str
    company: str
    description_text: str
    description_pdf_path: Optional[str] = None
    description_image_path: Optional[str] = None
    requirements: Optional[str] = None
    skills_required: Optional[str] = None  # JSON string
    experience_level: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Resume:
    """Data class for resumes"""

    candidate_name: str
    resume_text: str
    email: Optional[str] = None
    phone: Optional[str] = None
    resume_pdf_path: Optional[str] = None
    resume_image_path: Optional[str] = None
    skills: Optional[str] = None  # JSON string
    experience_years: Optional[int] = None
    education: Optional[str] = None
    certifications: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Interview:
    """Data class for interviews"""

    session_id: str
    job_description_id: int
    resume_id: int
    interview_link: Optional[str] = None
    status: str = "scheduled"
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    interviewer_notes: Optional[str] = None
    candidate_feedback: Optional[str] = None
    technical_assessment: Optional[str] = None
    behavioral_assessment: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InterviewDatabaseOps:
    """Database operations class for interview application"""

    def __init__(self, db_path: str = "db/interview_database.db"):
        """
        Initialize database operations

        Args:
            db_path: Path to SQLite database file
        """
        self.db_manager = DatabaseManager(db_path)

    # ==================== JOB DESCRIPTIONS ====================

    def create_job_description(self, job_desc: JobDescription) -> Optional[int]:
        """
        Create a new job description

        Args:
            job_desc: JobDescription object

        Returns:
            int: ID of created job description, None if failed
        """
        try:
            query = """
            INSERT INTO job_descriptions 
            (title, company, description_text, description_pdf_path, description_image_path,
             requirements, skills_required, experience_level, location, salary_range, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                job_desc.title,
                job_desc.company,
                job_desc.description_text,
                job_desc.description_pdf_path,
                job_desc.description_image_path,
                job_desc.requirements,
                job_desc.skills_required,
                job_desc.experience_level,
                job_desc.location,
                job_desc.salary_range,
                job_desc.is_active,
            )

            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                job_id = cursor.lastrowid
                logger.info(f"Created job description with ID: {job_id}")
                return job_id

        except Exception as e:
            logger.error(f"Error creating job description: {e}")
            return None

    def get_job_description(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job description by ID"""
        try:
            query = "SELECT * FROM job_descriptions WHERE id = ?"
            rows = self.db_manager.execute_query(query, (job_id,))
            if rows:
                return dict(rows[0])
            return None
        except Exception as e:
            logger.error(f"Error getting job description: {e}")
            return None

    def list_job_descriptions(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all job descriptions"""
        try:
            if active_only:
                query = "SELECT * FROM job_descriptions WHERE is_active = 1 ORDER BY created_at DESC"
            else:
                query = "SELECT * FROM job_descriptions ORDER BY created_at DESC"

            rows = self.db_manager.execute_query(query)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error listing job descriptions: {e}")
            return []

    def update_job_description(self, job_id: int, updates: Dict[str, Any]) -> bool:
        """Update job description"""
        try:
            # Build dynamic update query
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            query = f"""
            UPDATE job_descriptions 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """

            params = list(updates.values()) + [job_id]
            return self.db_manager.execute_update(query, tuple(params))

        except Exception as e:
            logger.error(f"Error updating job description: {e}")
            return False

    # ==================== RESUMES ====================

    def create_resume(self, resume: Resume) -> Optional[int]:
        """Create a new resume"""
        try:
            query = """
            INSERT INTO resumes 
            (candidate_name, email, phone, resume_text, resume_pdf_path, resume_image_path,
             skills, experience_years, education, certifications, linkedin_url, portfolio_url, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                resume.candidate_name,
                resume.email,
                resume.phone,
                resume.resume_text,
                resume.resume_pdf_path,
                resume.resume_image_path,
                resume.skills,
                resume.experience_years,
                resume.education,
                resume.certifications,
                resume.linkedin_url,
                resume.portfolio_url,
                resume.is_active,
            )

            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                resume_id = cursor.lastrowid
                logger.info(f"Created resume with ID: {resume_id}")
                return resume_id

        except Exception as e:
            logger.error(f"Error creating resume: {e}")
            return None

    def get_resume(self, resume_id: int) -> Optional[Dict[str, Any]]:
        """Get resume by ID"""
        try:
            query = "SELECT * FROM resumes WHERE id = ?"
            rows = self.db_manager.execute_query(query, (resume_id,))
            if rows:
                return dict(rows[0])
            return None
        except Exception as e:
            logger.error(f"Error getting resume: {e}")
            return None

    def find_resume_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find resume by candidate email"""
        try:
            query = "SELECT * FROM resumes WHERE email = ? AND is_active = 1"
            rows = self.db_manager.execute_query(query, (email,))
            if rows:
                return dict(rows[0])
            return None
        except Exception as e:
            logger.error(f"Error finding resume by email: {e}")
            return None

    def list_resumes(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all resumes"""
        try:
            if active_only:
                query = (
                    "SELECT * FROM resumes WHERE is_active = 1 ORDER BY created_at DESC"
                )
            else:
                query = "SELECT * FROM resumes ORDER BY created_at DESC"

            rows = self.db_manager.execute_query(query)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error listing resumes: {e}")
            return []

    # ==================== INTERVIEWS ====================

    def create_interview(self, interview: Interview) -> Optional[int]:
        """Create a new interview"""
        try:
            # Generate session_id if not provided
            if not interview.session_id:
                interview.session_id = str(uuid.uuid4())

            query = """
            INSERT INTO interviews 
            (session_id, job_description_id, resume_id, interview_link, status,
             scheduled_at, started_at, ended_at, duration_minutes, interviewer_notes,
             candidate_feedback, technical_assessment, behavioral_assessment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                interview.session_id,
                interview.job_description_id,
                interview.resume_id,
                interview.interview_link,
                interview.status,
                interview.scheduled_at,
                interview.started_at,
                interview.ended_at,
                interview.duration_minutes,
                interview.interviewer_notes,
                interview.candidate_feedback,
                interview.technical_assessment,
                interview.behavioral_assessment,
            )

            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                interview_id = cursor.lastrowid
                logger.info(f"Created interview with ID: {interview_id}")

                # Log system event
                self.log_system_event("interview_created", "interview", interview_id)

                return interview_id

        except Exception as e:
            logger.error(f"Error creating interview: {e}")
            return None

    def get_interview(self, interview_id: int) -> Optional[Dict[str, Any]]:
        """Get interview by ID"""
        try:
            query = "SELECT * FROM interviews WHERE id = ?"
            rows = self.db_manager.execute_query(query, (interview_id,))
            if rows:
                return dict(rows[0])
            return None
        except Exception as e:
            logger.error(f"Error getting interview: {e}")
            return None

    def get_interview_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get interview by session ID"""
        try:
            query = "SELECT * FROM interviews WHERE session_id = ?"
            rows = self.db_manager.execute_query(query, (session_id,))
            if rows:
                return dict(rows[0])
            return None
        except Exception as e:
            logger.error(f"Error getting interview by session: {e}")
            return None

    def update_interview_status(
        self,
        interview_id: int,
        status: str,
        additional_updates: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update interview status and optional additional fields"""
        try:
            updates = {"status": status, "updated_at": datetime.now().isoformat()}

            # Add status-specific updates
            if status == "in_progress" and not additional_updates:
                updates["started_at"] = datetime.now().isoformat()
            elif status == "completed":
                updates["ended_at"] = datetime.now().isoformat()

                # Calculate duration if started_at exists
                interview = self.get_interview(interview_id)
                if interview and interview.get("started_at"):
                    started = datetime.fromisoformat(interview["started_at"])
                    ended = datetime.now()
                    duration = int((ended - started).total_seconds() / 60)
                    updates["duration_minutes"] = duration

            # Add any additional updates
            if additional_updates:
                updates.update(additional_updates)

            return self.update_interview(interview_id, updates)

        except Exception as e:
            logger.error(f"Error updating interview status: {e}")
            return False

    def update_interview_using_session_id(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update interview with arbitrary fields"""
        try:
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            query = f"""
            UPDATE interviews 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
            """

            params = list(updates.values()) + [session_id]
            success = self.db_manager.execute_update(query, tuple(params))

            if success:
                self.log_system_event("interview_updated", "interview", session_id)

            return success

        except Exception as e:
            logger.error(f"Error updating interview: {e}")
            return False

    def update_interview(self, interview_id: int, updates: Dict[str, Any]) -> bool:
        """Update interview with arbitrary fields"""
        try:
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            query = f"""
            UPDATE interviews 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """

            params = list(updates.values()) + [interview_id]
            success = self.db_manager.execute_update(query, tuple(params))

            if success:
                self.log_system_event("interview_updated", "interview", interview_id)

            return success

        except Exception as e:
            logger.error(f"Error updating interview: {e}")
            return False

    def list_interviews(
        self, status_filter: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List all interviews with optional filters"""
        try:
            query = """
            SELECT i.*, 
                   jd.title as job_title, jd.company,
                   r.candidate_name, r.email
            FROM interviews i
            JOIN job_descriptions jd ON i.job_description_id = jd.id
            JOIN resumes r ON i.resume_id = r.id
            """
            params = []

            if status_filter:
                query += " WHERE i.status = ?"
                params.append(status_filter)

            query += " ORDER BY i.created_at DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            results = self.db_manager.execute_query(
                query, tuple(params) if params else None
            )
            return [dict(row) for row in results] if results else []

        except Exception as e:
            logger.error(f"Error listing interviews: {e}")
            return []

    def get_interview_summary(self, interview_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive interview summary with related data"""
        try:
            query = """
            SELECT i.*, 
                   jd.title as job_title, jd.company,
                   r.candidate_name, r.email,
                   mr.overall_match_score,
                   fs.final_score, fs.final_decision
            FROM interviews i
            JOIN job_descriptions jd ON i.job_description_id = jd.id
            JOIN resumes r ON i.resume_id = r.id
            LEFT JOIN match_ratings mr ON i.job_description_id = mr.job_description_id 
                                       AND i.resume_id = mr.resume_id
            LEFT JOIN final_scores fs ON i.id = fs.interview_id
            WHERE i.id = ?
            """

            results = self.db_manager.execute_query(query, (interview_id,))
            return dict(results[0]) if results else None

        except Exception as e:
            logger.error(f"Error getting interview summary: {e}")
            return None

    # ==================== MATCH RATINGS ====================

    def create_match_rating(
        self,
        job_description_id: int,
        resume_id: int,
        overall_score: float,
        reasoning: str,
        detailed_analysis: Optional[Dict[str, Any]] = None,
        model_version: Optional[str] = None,
    ) -> Optional[int]:
        """Create or update match rating between job and resume"""
        try:
            # Check if rating already exists
            existing = self.get_match_rating(job_description_id, resume_id)

            if existing:
                # Update existing rating
                updates = {
                    "overall_match_score": overall_score,
                    "match_reasoning": reasoning,
                    "detailed_analysis": (
                        json.dumps(detailed_analysis) if detailed_analysis else None
                    ),
                    "model_version": model_version,
                    "generated_at": datetime.now().isoformat(),
                }

                success = self.update_match_rating(existing["id"], updates)
                return existing["id"] if success else None

            else:
                # Create new rating
                query = """
                INSERT INTO match_ratings 
                (job_description_id, resume_id, overall_match_score, match_reasoning,
                 detailed_analysis, model_version)
                VALUES (?, ?, ?, ?, ?, ?)
                """

                params = (
                    job_description_id,
                    resume_id,
                    overall_score,
                    reasoning,
                    json.dumps(detailed_analysis) if detailed_analysis else None,
                    model_version,
                )

                with self.db_manager.get_connection() as conn:
                    cursor = conn.execute(query, params)
                    conn.commit()
                    rating_id = cursor.lastrowid
                    logger.info(f"Created match rating with ID: {rating_id}")
                    return rating_id

        except Exception as e:
            logger.error(f"Error creating match rating: {e}")
            return None

    def get_match_rating(
        self, job_description_id: int, resume_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get match rating for job and resume pair"""
        try:
            query = """
            SELECT * FROM match_ratings 
            WHERE job_description_id = ? AND resume_id = ?
            """
            rows = self.db_manager.execute_query(query, (job_description_id, resume_id))
            if rows:
                return dict(rows[0])
            return None
        except Exception as e:
            logger.error(f"Error getting match rating: {e}")
            return None

    def update_match_rating(self, rating_id: int, updates: Dict[str, Any]) -> bool:
        """Update match rating"""
        try:
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            query = f"""
            UPDATE match_ratings 
            SET {set_clause}
            WHERE id = ?
            """

            params = list(updates.values()) + [rating_id]
            return self.db_manager.execute_update(query, tuple(params))

        except Exception as e:
            logger.error(f"Error updating match rating: {e}")
            return False

    # ==================== INTERVIEW RECORDINGS ====================

    def add_interview_recording(
        self,
        interview_id: int,
        recording_type: str,
        file_path: Optional[str] = None,
        transcript_text: Optional[str] = None,
        **kwargs,
    ) -> Optional[int]:
        """Add interview recording/transcript"""
        try:
            query = """
            INSERT INTO interview_recordings 
            (interview_id, recording_type, file_path, transcript_text, transcript_jsonl_path,
             formatted_transcript_path, duration_seconds, file_size_mb, mime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                interview_id,
                recording_type,
                file_path,
                transcript_text,
                kwargs.get("transcript_jsonl_path"),
                kwargs.get("formatted_transcript_path"),
                kwargs.get("duration_seconds"),
                kwargs.get("file_size_mb"),
                kwargs.get("mime_type"),
            )

            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                recording_id = cursor.lastrowid
                logger.info(f"Added interview recording with ID: {recording_id}")
                return recording_id

        except Exception as e:
            logger.error(f"Error adding interview recording: {e}")
            return None

    def get_interview_recordings(self, interview_id: int) -> List[Dict[str, Any]]:
        """Get all recordings for an interview"""
        try:
            query = "SELECT * FROM interview_recordings WHERE interview_id = ? ORDER BY created_at"
            rows = self.db_manager.execute_query(query, (interview_id,))
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting interview recordings: {e}")
            return []

    # ==================== SCORING AND FINAL SCORES ====================

    def create_scoring_analysis(
        self,
        interview_id: int,
        scores: Dict[str, Any],
        model_version: Optional[str] = None,
    ) -> Optional[int]:
        """Create detailed scoring analysis"""
        try:
            query = """
            INSERT INTO scoring_analysis 
            (interview_id, technical_skills_score, technical_skills_reasoning,
             problem_solving_score, problem_solving_reasoning, communication_score,
             communication_reasoning, cultural_fit_score, cultural_fit_reasoning,
             resume_match_score, interview_performance_score, overall_impression_score,
             overall_impression_reasoning, key_strengths, areas_for_improvement,
             detailed_feedback, recommendation, recommendation_reasoning, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                interview_id,
                scores.get("technical_skills_score"),
                scores.get("technical_skills_reasoning"),
                scores.get("problem_solving_score"),
                scores.get("problem_solving_reasoning"),
                scores.get("communication_score"),
                scores.get("communication_reasoning"),
                scores.get("cultural_fit_score"),
                scores.get("cultural_fit_reasoning"),
                scores.get("resume_match_score"),
                scores.get("interview_performance_score"),
                scores.get("overall_impression_score"),
                scores.get("overall_impression_reasoning"),
                json.dumps(scores.get("key_strengths", [])),
                json.dumps(scores.get("areas_for_improvement", [])),
                scores.get("detailed_feedback"),
                scores.get("recommendation"),
                scores.get("recommendation_reasoning"),
                model_version,
            )

            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                analysis_id = cursor.lastrowid
                logger.info(f"Created scoring analysis with ID: {analysis_id}")
                return analysis_id

        except Exception as e:
            logger.error(f"Error creating scoring analysis: {e}")
            return None

    def create_final_score(
        self, interview_id: int, final_score: float, decision: str, **kwargs
    ) -> Optional[int]:
        """Create final score and decision"""
        try:
            query = """
            INSERT INTO final_scores 
            (interview_id, final_score, weighted_technical_score, weighted_behavioral_score,
             weighted_communication_score, weighted_cultural_fit_score, scoring_methodology,
             pass_fail_status, confidence_level, human_review_required, final_decision,
             decision_reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            pass_fail = "pass" if final_score >= 6.0 else "fail"  # Default threshold

            params = (
                interview_id,
                final_score,
                kwargs.get("weighted_technical_score"),
                kwargs.get("weighted_behavioral_score"),
                kwargs.get("weighted_communication_score"),
                kwargs.get("weighted_cultural_fit_score"),
                kwargs.get("scoring_methodology"),
                pass_fail,
                kwargs.get("confidence_level"),
                kwargs.get("human_review_required", False),
                decision,
                kwargs.get("decision_reasoning"),
            )

            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                score_id = cursor.lastrowid
                logger.info(f"Created final score with ID: {score_id}")

                # Log system event
                self.log_system_event("final_score_generated", "final_scores", score_id)

                return score_id

        except Exception as e:
            logger.error(f"Error creating final score: {e}")
            return None

    def get_interview_full_results(self, interview_id: int) -> Dict[str, Any]:
        """Get complete interview results including all related data"""
        try:
            results = {}

            # Get interview details
            interview = self.get_interview(interview_id)
            if not interview:
                return {}

            results["interview"] = interview

            # Get job description and resume
            results["job_description"] = self.get_job_description(
                interview["job_description_id"]
            )
            results["resume"] = self.get_resume(interview["resume_id"])

            # Get match rating
            results["match_rating"] = self.get_match_rating(
                interview["job_description_id"], interview["resume_id"]
            )

            # Get recordings and transcripts
            results["recordings"] = self.get_interview_recordings(interview_id)

            # Get scoring analysis
            query = "SELECT * FROM scoring_analysis WHERE interview_id = ?"
            rows = self.db_manager.execute_query(query, (interview_id,))
            results["scoring_analysis"] = dict(rows[0]) if rows else None

            # Get final score
            query = "SELECT * FROM final_scores WHERE interview_id = ?"
            rows = self.db_manager.execute_query(query, (interview_id,))
            results["final_score"] = dict(rows[0]) if rows else None

            # Get interview feedback
            query = "SELECT * FROM interview_feedback WHERE interview_id = ? ORDER BY created_at"
            rows = self.db_manager.execute_query(query, (interview_id,))
            results["feedback"] = [dict(row) for row in rows]

            return results

        except Exception as e:
            logger.error(f"Error getting interview full results: {e}")
            return {}

    def get_all_interview_results(self) -> Dict[str, Any]:
        """Get complete interview results including all related data"""
        try:
            results = {}

            # Get scoring analysis
            query = "SELECT * FROM scoring_analysis"
            rows = self.db_manager.execute_query(query)
            results["scoring_analysis"] = rows if rows else None

            # Get final score
            query = "SELECT * FROM final_scores"
            rows = self.db_manager.execute_query(query)
            results["final_score"] = rows if rows else None

            return results

        except Exception as e:
            logger.error(f"Error getting interview full results: {e}")
            return {}

    # ==================== SYSTEM EVENTS ====================

    def log_system_event(
        self,
        event_type: str,
        entity_type: str = None,
        entity_id: int = None,
        event_data: Dict[str, Any] = None,
        user_id: str = None,
    ) -> Optional[int]:
        """Log system event"""
        try:
            query = """
            INSERT INTO system_events 
            (event_type, entity_type, entity_id, event_data, user_id)
            VALUES (?, ?, ?, ?, ?)
            """

            params = (
                event_type,
                entity_type,
                entity_id,
                json.dumps(event_data) if event_data else None,
                user_id,
            )

            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error logging system event: {e}")
            return None

    # ==================== UTILITY METHODS ====================

    def get_recent_interviews(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent interviews"""
        try:
            query = """
            SELECT * FROM interview_summary 
            WHERE started_at > datetime('now', '-{} days')
            ORDER BY started_at DESC
            """.format(
                days
            )

            rows = self.db_manager.execute_query(query)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent interviews: {e}")
            return []

    def search_candidates(self, search_term: str) -> List[Dict[str, Any]]:
        """Search candidates by name or email"""
        try:
            query = """
            SELECT * FROM resumes 
            WHERE (candidate_name LIKE ? OR email LIKE ?) AND is_active = 1
            ORDER BY candidate_name
            """

            term = f"%{search_term}%"
            rows = self.db_manager.execute_query(query, (term, term))
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error searching candidates: {e}")
            return []


# Convenience functions for easy import
def get_db_ops(db_path: str = "db/interview_database.db") -> InterviewDatabaseOps:
    """Get database operations instance"""
    return InterviewDatabaseOps(db_path)
