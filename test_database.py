#!/usr/bin/env python3
"""
Test script for SQLite database functionality
Creates sample data and validates all database operations
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from init_database import DatabaseManager
from database_operations import (
    InterviewDatabaseOps,
    JobDescription,
    Resume,
    Interview,
    get_db_ops,
)


def create_sample_job_description() -> JobDescription:
    """Create sample job description"""
    skills = json.dumps(
        [
            "Python",
            "Machine Learning",
            "GenAI",
            "Vertex AI",
            "Google Cloud",
            "RAG",
            "Vector Databases",
            "Flask",
            "Streamlit",
        ]
    )

    return JobDescription(
        title="GenAI Specialist",
        company="Tech Innovations Inc",
        description_text="""We are looking for a GenAI Specialist to join our AI team. 
        The candidate will work on cutting-edge AI projects involving RAG pipelines, 
        vector databases, and LLM applications.""",
        requirements="Bachelor's degree in Computer Science or related field. 3+ years of experience.",
        skills_required=skills,
        experience_level="Mid-level",
        location="Remote",
        salary_range="$80,000 - $120,000",
    )


def create_sample_resume() -> Resume:
    """Create sample resume"""
    skills = json.dumps(
        [
            "Python",
            "Vertex AI",
            "Machine Learning",
            "Flask",
            "Streamlit",
            "Google Cloud",
            "GenAI",
            "Problem Solving",
        ]
    )

    return Resume(
        candidate_name="Himanshu Gohil",
        email="himanshu.gohil@example.com",
        phone="+1-555-0123",
        resume_text="""GenAI Specialist at Google with 3 years of experience in developing
        AI solutions using Vertex AI and Python. Expertise in RAG pipelines, vector databases,
        and LLM applications. Strong background in cloud computing and automation.""",
        skills=skills,
        experience_years=3,
        education="Bachelor's in Computer Science",
        certifications="Google Cloud Professional ML Engineer",
        linkedin_url="https://linkedin.com/in/himanshugohil",
        portfolio_url="https://himanshugohil.dev",
    )


def create_sample_interview(job_id: int, resume_id: int) -> Interview:
    """Create sample interview"""
    return Interview(
        session_id="session_20250929_065236",
        job_description_id=job_id,
        resume_id=resume_id,
        interview_link="https://meet.google.com/abc-defg-hij",
        status="completed",
        scheduled_at=(datetime.now() - timedelta(hours=2)).isoformat(),
        started_at=(datetime.now() - timedelta(hours=1, minutes=30)).isoformat(),
        ended_at=(datetime.now() - timedelta(minutes=30)).isoformat(),
        duration_minutes=60,
        interviewer_notes="Candidate showed good technical knowledge",
        technical_assessment="Strong understanding of RAG pipelines and Vertex AI",
        behavioral_assessment="Good communication skills, team player",
    )


def run_comprehensive_tests():
    """Run comprehensive database tests"""
    print("=" * 80)
    print("SQLite Database Comprehensive Testing")
    print("=" * 80)

    # Initialize database
    print("\n1. Initializing Database...")
    db_ops = get_db_ops("db/test_interview_database.db")

    # Create database
    success = db_ops.db_manager.create_database(force_recreate=True)
    if not success:
        print("❌ Failed to create database")
        return False
    print("✅ Database created successfully")

    # Test Job Descriptions
    print("\n2. Testing Job Descriptions...")
    job_desc = create_sample_job_description()
    job_id = db_ops.create_job_description(job_desc)
    if not job_id:
        print("❌ Failed to create job description")
        return False
    print(f"✅ Created job description with ID: {job_id}")

    # Test retrieving job description
    retrieved_job = db_ops.get_job_description(job_id)
    if not retrieved_job:
        print("❌ Failed to retrieve job description")
        return False
    print(f"✅ Retrieved job description: {retrieved_job['title']}")

    # Test Resumes
    print("\n3. Testing Resumes...")
    resume = create_sample_resume()
    resume_id = db_ops.create_resume(resume)
    if not resume_id:
        print("❌ Failed to create resume")
        return False
    print(f"✅ Created resume with ID: {resume_id}")

    # Test retrieving resume
    retrieved_resume = db_ops.get_resume(resume_id)
    if not retrieved_resume:
        print("❌ Failed to retrieve resume")
        return False
    print(f"✅ Retrieved resume: {retrieved_resume['candidate_name']}")

    # Test Match Rating
    print("\n4. Testing Match Ratings...")
    match_analysis = {
        "skills_match": 0.9,
        "experience_match": 0.8,
        "requirements_match": 0.85,
        "detailed_breakdown": {
            "matching_skills": ["Python", "Vertex AI", "GenAI"],
            "missing_skills": ["Pinecone", "Chroma"],
            "experience_assessment": "Meets minimum requirements",
        },
    }

    rating_id = db_ops.create_match_rating(
        job_id,
        resume_id,
        87.5,
        "Strong match with minor gaps in vector database experience",
        match_analysis,
        "gemini-2.5-pro",
    )
    if not rating_id:
        print("❌ Failed to create match rating")
        return False
    print(f"✅ Created match rating with ID: {rating_id}")

    # Test Interviews
    print("\n5. Testing Interviews...")
    interview = create_sample_interview(job_id, resume_id)
    interview_id = db_ops.create_interview(interview)
    if not interview_id:
        print("❌ Failed to create interview")
        return False
    print(f"✅ Created interview with ID: {interview_id}")

    # Test updating interview status
    success = db_ops.update_interview_status(interview_id, "completed")
    if not success:
        print("❌ Failed to update interview status")
        return False
    print("✅ Updated interview status")

    # Test Interview Recordings
    print("\n6. Testing Interview Recordings...")
    recording_id = db_ops.add_interview_recording(
        interview_id,
        "transcript",
        transcript_text="This is a sample transcript of the interview...",
        transcript_jsonl_path="recordings/session_20250929_065236_transcripts.jsonl",
        formatted_transcript_path="recordings/session_20250929_065236_formatted_transcript.txt",
        duration_seconds=3600,
    )
    if not recording_id:
        print("❌ Failed to add interview recording")
        return False
    print(f"✅ Added interview recording with ID: {recording_id}")

    # Test Scoring Analysis
    print("\n7. Testing Scoring Analysis...")
    scoring_data = {
        "technical_skills_score": 7.5,
        "technical_skills_reasoning": "Good understanding of GenAI concepts",
        "problem_solving_score": 6.0,
        "problem_solving_reasoning": "Decent problem-solving approach but could be more structured",
        "communication_score": 8.0,
        "communication_reasoning": "Clear and articulate communication",
        "cultural_fit_score": 7.0,
        "cultural_fit_reasoning": "Aligns well with company values",
        "resume_match_score": 8.5,
        "interview_performance_score": 7.0,
        "overall_impression_score": 7.5,
        "overall_impression_reasoning": "Strong candidate with good potential",
        "key_strengths": ["Technical expertise", "Communication", "Experience"],
        "areas_for_improvement": ["Problem-solving methodology", "Broader tech stack"],
        "detailed_feedback": "Candidate shows strong technical knowledge...",
        "recommendation": "hire",
        "recommendation_reasoning": "Good fit for the role with growth potential",
    }

    analysis_id = db_ops.create_scoring_analysis(
        interview_id, scoring_data, "gemini-2.5-pro"
    )
    if not analysis_id:
        print("❌ Failed to create scoring analysis")
        return False
    print(f"✅ Created scoring analysis with ID: {analysis_id}")

    # Test Final Score
    print("\n8. Testing Final Scores...")
    final_score_id = db_ops.create_final_score(
        interview_id,
        7.3,
        "hire",
        weighted_technical_score=7.5,
        weighted_behavioral_score=7.0,
        weighted_communication_score=8.0,
        weighted_cultural_fit_score=7.0,
        scoring_methodology="Weighted average of all assessment criteria",
        confidence_level=0.85,
        decision_reasoning="Candidate meets requirements and shows good potential",
    )
    if not final_score_id:
        print("❌ Failed to create final score")
        return False
    print(f"✅ Created final score with ID: {final_score_id}")

    # Test Full Results Retrieval
    print("\n9. Testing Full Results Retrieval...")
    full_results = db_ops.get_interview_full_results(interview_id)
    if not full_results:
        print("❌ Failed to get full interview results")
        return False
    print("✅ Retrieved full interview results")
    print(f"   - Candidate: {full_results['resume']['candidate_name']}")
    print(f"   - Job: {full_results['job_description']['title']}")
    print(f"   - Match Score: {full_results['match_rating']['overall_match_score']}")
    print(f"   - Final Score: {full_results['final_score']['final_score']}")
    print(f"   - Decision: {full_results['final_score']['final_decision']}")

    # Test Search and List Operations
    print("\n10. Testing Search and List Operations...")

    # List job descriptions
    jobs = db_ops.list_job_descriptions()
    print(f"✅ Listed {len(jobs)} job descriptions")

    # List resumes
    resumes = db_ops.list_resumes()
    print(f"✅ Listed {len(resumes)} resumes")

    # Search candidates
    candidates = db_ops.search_candidates("Himanshu")
    print(f"✅ Found {len(candidates)} candidates matching search")

    # Get recent interviews
    recent = db_ops.get_recent_interviews(7)
    print(f"✅ Found {len(recent)} recent interviews")

    # Test Database Statistics
    print("\n11. Testing Database Statistics...")
    stats = db_ops.db_manager.get_database_stats()
    print("✅ Database Statistics:")
    for key, value in stats.items():
        print(f"   - {key.replace('_', ' ').title()}: {value}")

    # Test System Events
    print("\n12. Testing System Events...")
    event_id = db_ops.log_system_event(
        "test_completed",
        "database",
        None,
        {"test_status": "success", "timestamp": datetime.now().isoformat()},
    )
    if not event_id:
        print("❌ Failed to log system event")
        return False
    print(f"✅ Logged system event with ID: {event_id}")

    # Validate database integrity
    print("\n13. Validating Database Integrity...")
    valid = db_ops.db_manager.validate_database()
    if not valid:
        print("❌ Database validation failed")
        return False
    print("✅ Database validation passed")

    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED! Database is working correctly.")
    print("=" * 80)

    return True


def create_production_sample_data():
    """Create sample data for production database"""
    print("\n" + "=" * 80)
    print("Creating Sample Data for Production Database")
    print("=" * 80)

    db_ops = get_db_ops("db/interview_database.db")

    # Create sample job descriptions
    jobs_data = [
        {
            "title": "Senior GenAI Engineer",
            "company": "AI Innovations Corp",
            "description_text": "Lead GenAI initiatives and develop cutting-edge AI solutions",
            "skills_required": json.dumps(
                ["Python", "TensorFlow", "PyTorch", "GenAI", "MLOps"]
            ),
            "experience_level": "Senior",
            "location": "San Francisco, CA",
            "salary_range": "$130,000 - $180,000",
        },
        {
            "title": "ML Engineer - RAG Specialist",
            "company": "Data Solutions Inc",
            "description_text": "Specialize in RAG pipelines and vector database optimization",
            "skills_required": json.dumps(
                ["Python", "RAG", "Vector Databases", "LangChain", "ChromaDB"]
            ),
            "experience_level": "Mid-level",
            "location": "Remote",
            "salary_range": "$90,000 - $130,000",
        },
    ]

    # Create sample resumes
    resumes_data = [
        {
            "candidate_name": "Alice Johnson",
            "email": "alice.johnson@email.com",
            "resume_text": "Experienced ML Engineer with 5 years in GenAI development",
            "skills": json.dumps(["Python", "TensorFlow", "GenAI", "MLOps", "AWS"]),
            "experience_years": 5,
        },
        {
            "candidate_name": "Bob Smith",
            "email": "bob.smith@email.com",
            "resume_text": "RAG specialist with expertise in vector databases and LLM optimization",
            "skills": json.dumps(
                ["Python", "RAG", "ChromaDB", "LangChain", "Pinecone"]
            ),
            "experience_years": 3,
        },
    ]

    print("Creating sample job descriptions...")
    job_ids = []
    for job_data in jobs_data:
        job_desc = JobDescription(**job_data)
        job_id = db_ops.create_job_description(job_desc)
        if job_id:
            job_ids.append(job_id)
            print(f"✅ Created job: {job_data['title']}")

    print("\nCreating sample resumes...")
    resume_ids = []
    for resume_data in resumes_data:
        resume = Resume(**resume_data)
        resume_id = db_ops.create_resume(resume)
        if resume_id:
            resume_ids.append(resume_id)
            print(f"✅ Created resume: {resume_data['candidate_name']}")

    print(f"\n✅ Sample data created successfully!")
    print(f"   - {len(job_ids)} job descriptions")
    print(f"   - {len(resume_ids)} resumes")

    return job_ids, resume_ids


def main():
    """Main test function"""
    print("Starting SQLite Database Tests...")

    # Run comprehensive tests
    test_success = run_comprehensive_tests()

    if test_success:
        print("\n" + "🔄" * 20)

        # Create production database with sample data
        print("Setting up production database...")
        db_manager = DatabaseManager("db/interview_database.db")
        prod_success = db_manager.create_database()

        if prod_success:
            print("✅ Production database created")
            job_ids, resume_ids = create_production_sample_data()

            print(f"\n🎉 Setup Complete!")
            print(f"Production database: interview_database.db")
            print(f"Test database: db/test_interview_database.db")
        else:
            print("❌ Failed to create production database")

    # Clean up test database (best-effort). On Windows the file may be in use by
    # another process (for example a running server) which will raise
    # PermissionError when trying to remove it. Attempt to close any local
    # connections, then retry removal a few times before giving up with a
    # helpful message.
    test_db_path = "db/test_interview_database.db"
    if os.path.exists(test_db_path):
        try:
            # Try to close any connection in this process and force a GC pass
            import sqlite3, gc, time

            gc.collect()
            try:
                conn = sqlite3.connect(test_db_path)
                conn.close()
            except Exception:
                # Ignore errors here; this is a best-effort attempt
                pass

            removed = False
            for attempt in range(5):
                try:
                    os.remove(test_db_path)
                    print(f"\n🧹 Cleaned up test database: {test_db_path}")
                    removed = True
                    break
                except PermissionError as e:
                    # File is locked by another process; wait and retry
                    print(
                        f"⚠️ Could not remove test database (attempt {attempt+1}/5): {e}"
                    )
                    time.sleep(0.5)

            if not removed:
                print(
                    f"\n❗ Unable to remove test database {test_db_path}. It may be in use by another process. "
                    "Please stop any running server or process that uses the DB and remove the file manually."
                )

        except Exception as e:
            # If something else goes wrong, print a message but don't raise
            print(f"⚠️ Exception during test DB cleanup: {e}")


if __name__ == "__main__":
    main()
