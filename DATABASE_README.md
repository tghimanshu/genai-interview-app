# SQLite Database for Live Interview App

This document provides comprehensive documentation for the SQLite database system designed for your live interview application.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Database Schema](#database-schema)
3. [Setup and Installation](#setup-and-installation)
4. [Usage Guide](#usage-guide)
5. [API Reference](#api-reference)
6. [Integration Examples](#integration-examples)
7. [Best Practices](#best-practices)

## 🎯 Overview

The SQLite database system stores all interview-related data including:

- **Job Descriptions** (PDF/image + text)
- **Resumes** (PDF/image + text)
- **Match Ratings and Reasoning**
- **Interview Links and Sessions**
- **Interview Recordings and Transcripts**
- **Scoring Analysis**
- **Feedback and Final Scores**
- **System Events and Audit Trail**

## 📊 Database Schema

### Core Tables

#### `job_descriptions`

Stores job posting information and requirements.

```sql
- id (PRIMARY KEY)
- title, company, description_text
- description_pdf_path, description_image_path
- requirements, skills_required (JSON)
- experience_level, location, salary_range
- created_at, updated_at, is_active
```

#### `resumes`

Stores candidate resume information.

```sql
- id (PRIMARY KEY)
- candidate_name, email, phone
- resume_text, resume_pdf_path, resume_image_path
- skills (JSON), experience_years, education
- certifications, linkedin_url, portfolio_url
- created_at, updated_at, is_active
```

#### `interviews`

Manages interview sessions and metadata.

```sql
- id (PRIMARY KEY)
- session_id (UNIQUE)
- job_description_id, resume_id (FOREIGN KEYS)
- interview_link, status
- scheduled_at, started_at, ended_at, duration_minutes
- interviewer_notes, candidate_feedback
- technical_assessment, behavioral_assessment
```

#### `match_ratings`

Stores AI-generated match scores between jobs and resumes.

```sql
- id (PRIMARY KEY)
- job_description_id, resume_id (FOREIGN KEYS)
- overall_match_score, skills_match_score
- experience_match_score, education_match_score
- match_reasoning, detailed_analysis (JSON)
- model_version, generated_at
```

#### `interview_recordings`

Stores interview media and transcripts.

```sql
- id (PRIMARY KEY)
- interview_id (FOREIGN KEY)
- recording_type ('audio', 'video', 'transcript')
- file_path, transcript_text
- transcript_jsonl_path, formatted_transcript_path
- duration_seconds, file_size_mb, mime_type
```

#### `scoring_analysis`

Detailed AI-generated interview evaluation.

```sql
- id (PRIMARY KEY)
- interview_id (FOREIGN KEY)
- technical_skills_score, technical_skills_reasoning
- problem_solving_score, problem_solving_reasoning
- communication_score, communication_reasoning
- cultural_fit_score, cultural_fit_reasoning
- resume_match_score, interview_performance_score
- overall_impression_score, key_strengths (JSON)
- areas_for_improvement (JSON), detailed_feedback
- recommendation, recommendation_reasoning
```

#### `final_scores`

Final hiring decision and composite scores.

```sql
- id (PRIMARY KEY)
- interview_id (FOREIGN KEY)
- final_score, weighted_technical_score
- weighted_behavioral_score, weighted_communication_score
- scoring_methodology, pass_fail_status
- confidence_level, human_review_required
- final_decision, decision_reasoning
- reviewed_by, reviewed_at
```

### Supporting Tables

- **`interview_feedback`** - Individual Q&A pairs and responses
- **`system_events`** - Audit trail and system logging

### Views

- **`interview_summary`** - Complete interview overview with joins
- **`candidate_performance`** - Aggregate candidate statistics

## 🚀 Setup and Installation

### 1. Initialize Database

```python
from init_database import DatabaseManager

# Create database with all tables
db_manager = DatabaseManager("db/interview_database.db")
success = db_manager.create_database()

if success:
    print("✅ Database created successfully")
```

### 2. Run Tests

```bash
# Test all database functionality
python test_database.py
```

### 3. Load Sample Data

```python
from database_usage_examples import main
main()  # Creates sample job descriptions and resumes
```

## 📖 Usage Guide

### Basic Operations

```python
from database_operations import get_db_ops, JobDescription, Resume, Interview

# Initialize database operations
db_ops = get_db_ops()

# Create job description
job_desc = JobDescription(
    title="Software Engineer",
    company="Tech Corp",
    description_text="We are hiring...",
    skills_required='["Python", "AI", "ML"]'
)
job_id = db_ops.create_job_description(job_desc)

# Create resume
resume = Resume(
    candidate_name="John Doe",
    email="john@example.com",
    resume_text="Experienced developer...",
    skills='["Python", "JavaScript", "React"]'
)
resume_id = db_ops.create_resume(resume)

# Create match rating
rating_id = db_ops.create_match_rating(
    job_id, resume_id, 85.5,
    "Strong technical match with relevant experience",
    {"skills_overlap": 0.8, "experience_match": 0.9}
)
```

### Interview Workflow

```python
# 1. Schedule interview
interview = Interview(
    session_id="session_20241201_143000",
    job_description_id=job_id,
    resume_id=resume_id,
    status="scheduled"
)
interview_id = db_ops.create_interview(interview)

# 2. Start interview
db_ops.update_interview_status(interview_id, "in_progress")

# 3. Add transcript
db_ops.add_interview_recording(
    interview_id, "transcript",
    transcript_text="Interview discussion content...",
    duration_seconds=3600
)

# 4. Complete interview
db_ops.update_interview_status(interview_id, "completed")

# 5. Generate scoring
scoring_data = {
    "technical_skills_score": 8.0,
    "communication_score": 7.5,
    "problem_solving_score": 8.2,
    "recommendation": "hire"
}
db_ops.create_scoring_analysis(interview_id, scoring_data)

# 6. Final decision
db_ops.create_final_score(
    interview_id, 7.9, "hire",
    confidence_level=0.85,
    decision_reasoning="Strong candidate with excellent technical skills"
)
```

### Querying Data

```python
# Get complete interview results
results = db_ops.get_interview_full_results(interview_id)
print(f"Final Decision: {results['final_score']['final_decision']}")
print(f"Score: {results['final_score']['final_score']}")

# Search candidates
candidates = db_ops.search_candidates("john")

# Get recent interviews
recent = db_ops.get_recent_interviews(days=7)

# List all jobs
jobs = db_ops.list_job_descriptions()
```

## 🔧 API Reference

### InterviewDatabaseOps Class

#### Job Descriptions

- `create_job_description(job_desc: JobDescription) -> Optional[int]`
- `get_job_description(job_id: int) -> Optional[Dict]`
- `list_job_descriptions(active_only: bool = True) -> List[Dict]`
- `update_job_description(job_id: int, updates: Dict) -> bool`

#### Resumes

- `create_resume(resume: Resume) -> Optional[int]`
- `get_resume(resume_id: int) -> Optional[Dict]`
- `find_resume_by_email(email: str) -> Optional[Dict]`
- `list_resumes(active_only: bool = True) -> List[Dict]`

#### Interviews

- `create_interview(interview: Interview) -> Optional[int]`
- `get_interview(interview_id: int) -> Optional[Dict]`
- `get_interview_by_session(session_id: str) -> Optional[Dict]`
- `update_interview_status(interview_id: int, status: str) -> bool`

#### Match Ratings

- `create_match_rating(job_id: int, resume_id: int, score: float, reasoning: str) -> Optional[int]`
- `get_match_rating(job_id: int, resume_id: int) -> Optional[Dict]`

#### Scoring & Results

- `create_scoring_analysis(interview_id: int, scores: Dict) -> Optional[int]`
- `create_final_score(interview_id: int, final_score: float, decision: str) -> Optional[int]`
- `get_interview_full_results(interview_id: int) -> Dict`

## 🔗 Integration Examples

### With app.py (Live Interview)

```python
# In your AudioLoop class
from database_operations import get_db_ops

class AudioLoop:
    def __init__(self):
        self.db_ops = get_db_ops()
        # ... existing code

    async def run(self):
        # Create interview record when session starts
        interview_id = self.db_ops.create_interview(Interview(
            session_id=self.session_id,
            job_description_id=self.job_id,  # from config
            resume_id=self.resume_id,       # from config
            status="in_progress"
        ))

        # ... existing interview logic

        # Save transcript when interview ends
        await self._save_interview_data(interview_id)

    async def _save_interview_data(self, interview_id):
        # Save transcript
        self.db_ops.add_interview_recording(
            interview_id, "transcript",
            transcript_text=self.transcript_content,
            duration_seconds=self.duration
        )

        # Update status
        self.db_ops.update_interview_status(interview_id, "completed")
```

### With score_candidate.py

```python
from database_operations import get_db_ops

def score_and_save_interview(session_id: str):
    db_ops = get_db_ops()

    # Get interview by session
    interview = db_ops.get_interview_by_session(session_id)
    if not interview:
        print("Interview not found!")
        return

    # Generate AI scoring (existing logic)
    response = client.models.generate_content(...)

    # Parse scoring results and save to database
    scoring_data = parse_ai_response(response.text)

    # Save scoring analysis
    analysis_id = db_ops.create_scoring_analysis(
        interview["id"], scoring_data, "gemini-2.5-pro"
    )

    # Save final score
    final_score_id = db_ops.create_final_score(
        interview["id"],
        scoring_data["final_score"],
        scoring_data["recommendation"]
    )

    print(f"Scoring saved - Analysis ID: {analysis_id}, Final Score ID: {final_score_id}")
```

### With server.py (FastAPI)

```python
from database_operations import get_db_ops

@app.post("/api/interviews")
async def create_interview_endpoint(job_id: int, resume_id: int):
    db_ops = get_db_ops()

    # Create interview record
    interview = Interview(
        session_id=generate_session_id(),
        job_description_id=job_id,
        resume_id=resume_id,
        status="scheduled"
    )

    interview_id = db_ops.create_interview(interview)
    return {"interview_id": interview_id, "session_id": interview.session_id}

@app.get("/api/interviews/{interview_id}/results")
async def get_interview_results(interview_id: int):
    db_ops = get_db_ops()
    results = db_ops.get_interview_full_results(interview_id)
    return results

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    db_ops = get_db_ops()
    stats = db_ops.db_manager.get_database_stats()
    recent = db_ops.get_recent_interviews(7)

    return {
        "database_stats": stats,
        "recent_interviews": len(recent),
        "recent_hires": len([i for i in recent if i.get('final_decision') == 'hire'])
    }
```

## 💡 Best Practices

### 1. Error Handling

```python
try:
    job_id = db_ops.create_job_description(job_desc)
    if not job_id:
        logger.error("Failed to create job description")
        return None
except Exception as e:
    logger.error(f"Database error: {e}")
    return None
```

### 2. Transaction Management

```python
# For complex operations, use database transactions
with db_ops.db_manager.get_connection() as conn:
    try:
        # Multiple operations
        job_id = db_ops.create_job_description(job_desc)
        resume_id = db_ops.create_resume(resume)
        interview_id = db_ops.create_interview(interview)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
```

### 3. Data Validation

```python
# Validate required fields before database operations
def validate_job_description(job_desc: JobDescription) -> bool:
    if not job_desc.title or not job_desc.company:
        return False
    if not job_desc.description_text:
        return False
    return True
```

### 4. Backup Strategy

```python
# Regular backups
from datetime import datetime

def backup_database():
    db_manager = DatabaseManager()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"backups/interview_db_backup_{timestamp}.db"
    return db_manager.backup_database(backup_path)
```

### 5. Performance Optimization

```python
# Use batch operations for multiple inserts
# Use database views for complex queries
# Index frequently queried columns
# Limit result sets with pagination

def get_paginated_interviews(page: int = 1, per_page: int = 20):
    offset = (page - 1) * per_page
    query = f"""
    SELECT * FROM interview_summary
    ORDER BY created_at DESC
    LIMIT {per_page} OFFSET {offset}
    """
    return db_ops.execute_query(query)
```

## 🔧 Maintenance

### Database Backup

```bash
# Create backup
python -c "from init_database import DatabaseManager; DatabaseManager().backup_database()"
```

### Database Statistics

```python
# Check database health
db_ops = get_db_ops()
stats = db_ops.db_manager.get_database_stats()
print(f"Database size: {stats['database_size_mb']} MB")
print(f"Total interviews: {stats['interviews_count']}")
```

### Cleanup Old Data

```python
# Archive old interviews (example)
def archive_old_interviews(days_old: int = 365):
    query = """
    UPDATE interviews
    SET is_active = 0
    WHERE created_at < datetime('now', '-{} days')
    """.format(days_old)
    return db_ops.db_manager.execute_update(query)
```

---

## 📞 Support

For questions or issues with the database system:

1. Check the test files for examples
2. Review the database schema documentation
3. Use logging to debug database operations
4. Check system_events table for audit information

The database system is designed to be robust, scalable, and easy to integrate with your existing interview application workflow.
