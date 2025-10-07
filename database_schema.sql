-- SQLite Database Schema for Live Interview App
-- This schema supports storing job descriptions, resumes, interviews, scoring, and feedback

-- Table to store job descriptions
CREATE TABLE job_descriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    description_text TEXT NOT NULL,
    description_pdf_path VARCHAR(500),
    description_image_path VARCHAR(500),
    requirements TEXT,
    skills_required TEXT, -- JSON format for structured skills
    experience_level VARCHAR(50),
    location VARCHAR(255),
    salary_range VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Table to store candidate resumes
CREATE TABLE resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    resume_text TEXT NOT NULL,
    resume_pdf_path VARCHAR(500),
    resume_image_path VARCHAR(500),
    skills TEXT, -- JSON format for structured skills
    experience_years INTEGER,
    education TEXT,
    certifications TEXT,
    linkedin_url VARCHAR(500),
    portfolio_url VARCHAR(500),
    github_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Table to store interview sessions
CREATE TABLE interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    job_description_id INTEGER NOT NULL,
    resume_id INTEGER NOT NULL,
    interview_link VARCHAR(500),
    status VARCHAR(50) DEFAULT 'scheduled', -- scheduled, in_progress, completed, cancelled
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_minutes INTEGER,
    interviewer_notes TEXT,
    candidate_feedback TEXT,
    technical_assessment TEXT,
    behavioral_assessment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_description_id) REFERENCES job_descriptions(id),
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
);

-- Table to store match ratings between resume and job description
CREATE TABLE match_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_description_id INTEGER NOT NULL,
    resume_id INTEGER NOT NULL,
    overall_match_score REAL NOT NULL, -- 0-100 scale
    skills_match_score REAL,
    experience_match_score REAL,
    education_match_score REAL,
    requirements_match_score REAL,
    match_reasoning TEXT NOT NULL,
    detailed_analysis TEXT, -- JSON format for structured analysis
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(100),
    FOREIGN KEY (job_description_id) REFERENCES job_descriptions(id),
    FOREIGN KEY (resume_id) REFERENCES resumes(id),
    UNIQUE(job_description_id, resume_id) -- One rating per job-resume pair
);

-- Table to store interview transcriptions and recordings
CREATE TABLE interview_recordings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    recording_type VARCHAR(50) NOT NULL, -- 'audio', 'video', 'screen_share', 'transcript'
    file_path VARCHAR(500),
    transcript_text TEXT,
    transcript_jsonl_path VARCHAR(500), -- Path to detailed JSONL transcript
    formatted_transcript_path VARCHAR(500), -- Path to formatted transcript
    duration_seconds INTEGER,
    file_size_mb REAL,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(id)
);

-- Table to store detailed scoring analysis
CREATE TABLE scoring_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    technical_skills_score REAL, -- 0-10 scale
    technical_skills_reasoning TEXT,
    problem_solving_score REAL,
    problem_solving_reasoning TEXT,
    communication_score REAL,
    communication_reasoning TEXT,
    cultural_fit_score REAL,
    cultural_fit_reasoning TEXT,
    resume_match_score REAL,
    interview_performance_score REAL,
    overall_impression_score REAL,
    overall_impression_reasoning TEXT,
    key_strengths TEXT, -- JSON array of strengths
    areas_for_improvement TEXT, -- JSON array of improvement areas
    detailed_feedback TEXT,
    recommendation VARCHAR(100), -- 'hire', 'reject', 'maybe', 'second_interview'
    recommendation_reasoning TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(100),
    FOREIGN KEY (interview_id) REFERENCES interviews(id)
);

-- Table to store final scores and decisions
CREATE TABLE final_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    final_score REAL NOT NULL, -- 0-10 scale
    weighted_technical_score REAL,
    weighted_behavioral_score REAL,
    weighted_communication_score REAL,
    weighted_cultural_fit_score REAL,
    scoring_methodology TEXT, -- Description of how final score was calculated
    pass_fail_status VARCHAR(20), -- 'pass', 'fail'
    confidence_level REAL, -- 0-1 scale indicating AI confidence in assessment
    human_review_required BOOLEAN DEFAULT FALSE,
    final_decision VARCHAR(100), -- 'hire', 'reject', 'second_interview', 'pending_review'
    decision_reasoning TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by VARCHAR(255), -- Human reviewer name/ID
    reviewed_at TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(id)
);

-- Table to store candidate feedback and answers
CREATE TABLE interview_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    question_type VARCHAR(100), -- 'technical', 'behavioral', 'situational', 'general'
    difficulty_level VARCHAR(20), -- 'easy', 'medium', 'hard'
    time_taken_seconds INTEGER,
    answer_quality_score REAL, -- 0-10 scale
    answer_analysis TEXT,
    follow_up_questions TEXT, -- JSON array of follow-up questions asked
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(id)
);

-- Table to track system events and audit trail
CREATE TABLE system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type VARCHAR(100) NOT NULL, -- 'interview_started', 'score_generated', 'file_uploaded', etc.
    entity_type VARCHAR(100), -- 'interview', 'resume', 'job_description', etc.
    entity_id INTEGER,
    event_data TEXT, -- JSON format for additional event details
    user_id VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX idx_interviews_session_id ON interviews(session_id);
CREATE INDEX idx_interviews_status ON interviews(status);
CREATE INDEX idx_interviews_job_description ON interviews(job_description_id);
CREATE INDEX idx_interviews_resume ON interviews(resume_id);
CREATE INDEX idx_match_ratings_scores ON match_ratings(overall_match_score);
CREATE INDEX idx_final_scores_score ON final_scores(final_score);
CREATE INDEX idx_final_scores_decision ON final_scores(final_decision);
CREATE INDEX idx_system_events_type ON system_events(event_type);
CREATE INDEX idx_system_events_entity ON system_events(entity_type, entity_id);

-- Views for common queries
CREATE VIEW interview_summary AS
SELECT 
    i.id as interview_id,
    i.session_id,
    i.status,
    jd.title as job_title,
    jd.company,
    r.candidate_name,
    r.email,
    mr.overall_match_score,
    fs.final_score,
    fs.final_decision,
    i.started_at,
    i.ended_at,
    i.duration_minutes,
    i.created_at
FROM interviews i
LEFT JOIN job_descriptions jd ON i.job_description_id = jd.id
LEFT JOIN resumes r ON i.resume_id = r.id
LEFT JOIN match_ratings mr ON (i.job_description_id = mr.job_description_id AND i.resume_id = mr.resume_id)
LEFT JOIN final_scores fs ON i.id = fs.interview_id;

CREATE VIEW candidate_performance AS
SELECT 
    r.candidate_name,
    r.email,
    COUNT(i.id) as total_interviews,
    AVG(fs.final_score) as average_score,
    COUNT(CASE WHEN fs.final_decision = 'hire' THEN 1 END) as hire_count,
    COUNT(CASE WHEN fs.final_decision = 'reject' THEN 1 END) as reject_count,
    MAX(i.created_at) as last_interview_date
FROM resumes r
LEFT JOIN interviews i ON r.id = i.resume_id
LEFT JOIN final_scores fs ON i.id = fs.interview_id
GROUP BY r.id, r.candidate_name, r.email;