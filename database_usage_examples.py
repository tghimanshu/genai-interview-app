#!/usr/bin/env python3
"""
Example usage of the SQLite database for the Live Interview App.

This module demonstrates how to use the `InterviewDatabaseOps` class to perform
various database operations, simulating a complete interview workflow from
job creation to final scoring and reporting.
"""

import json
from datetime import datetime
from pathlib import Path

from database_operations import (
    InterviewDatabaseOps, JobDescription, Resume, Interview, get_db_ops
)

def example_complete_interview_workflow():
    """
    Simulate a complete interview workflow.

    Steps:
    1. Create a job description.
    2. Create a candidate resume.
    3. Generate a match rating.
    4. Schedule an interview.
    5. Update interview status to 'in_progress'.
    6. Add an interview recording/transcript.
    7. Complete the interview.
    8. Generate scoring analysis.
    9. Create a final score and hiring decision.
    10. Retrieve complete results.

    Returns:
        int: The ID of the created interview.
    """
    print("=== Complete Interview Workflow Example ===\n")
    
    # Initialize database operations
    db_ops = get_db_ops()
    
    # 1. Create Job Description (from your existing files)
    print("1. Creating job description...")
    
    # Read existing job description file
    jd_file = Path("SDE_JD.txt")
    if jd_file.exists():
        with open(jd_file, 'r', encoding='utf-8') as f:
            jd_text = f.read()
    else:
        jd_text = "Software Engineer position requiring Python, AI/ML experience"
    
    job_desc = JobDescription(
        title="Software Development Engineer - GenAI",
        company="Your Company",
        description_text=jd_text,
        requirements="3+ years experience, Bachelor's degree",
        skills_required=json.dumps(["Python", "GenAI", "Machine Learning", "Vertex AI"]),
        experience_level="Mid-level",
        location="Remote/Hybrid",
        salary_range="$90,000 - $130,000"
    )
    
    job_id = db_ops.create_job_description(job_desc)
    print(f"✅ Job description created with ID: {job_id}")
    
    # 2. Create Resume (from your existing files)
    print("\n2. Processing candidate resume...")
    
    # Read existing resume file
    resume_file = Path("himanshu-resume.txt")
    if resume_file.exists():
        with open(resume_file, 'r', encoding='utf-8') as f:
            resume_text = f.read()
    else:
        resume_text = "Experienced GenAI specialist with Python and ML background"
    
    resume = Resume(
        candidate_name="Himanshu Gohil",
        email="himanshu.gohil@example.com",
        phone="+1-555-0123",
        resume_text=resume_text,
        resume_pdf_path="himanshu-resume.pdf",
        skills=json.dumps(["Python", "Vertex AI", "GenAI", "Google Cloud"]),
        experience_years=3,
        education="Bachelor's in Computer Science"
    )
    
    resume_id = db_ops.create_resume(resume)
    print(f"✅ Resume created with ID: {resume_id}")
    
    # 3. Generate Match Rating
    print("\n3. Generating match rating...")
    
    match_analysis = {
        "skills_match_percentage": 85,
        "experience_match": "Meets requirements",
        "education_match": "Qualified",
        "missing_skills": ["Docker", "Kubernetes"],
        "strong_points": ["GenAI expertise", "Google Cloud experience"]
    }
    
    rating_id = db_ops.create_match_rating(
        job_id, resume_id, 85.0,
        "Strong candidate match with relevant GenAI experience. Minor gaps in DevOps skills.",
        match_analysis,
        "gemini-2.5-pro"
    )
    print(f"✅ Match rating created: 85.0% match")
    
    # 4. Schedule Interview
    print("\n4. Creating interview session...")
    
    interview = Interview(
        session_id="session_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
        job_description_id=job_id,
        resume_id=resume_id,
        interview_link="https://meet.google.com/generated-link",
        status="scheduled",
        scheduled_at=datetime.now().isoformat()
    )
    
    interview_id = db_ops.create_interview(interview)
    print(f"✅ Interview scheduled with ID: {interview_id}")
    
    # 5. Start Interview (update status)
    print("\n5. Starting interview...")
    success = db_ops.update_interview_status(interview_id, "in_progress")
    print(f"✅ Interview started")
    
    # 6. Add Interview Recording/Transcript
    print("\n6. Adding interview transcript...")
    
    # Check if transcript files exist from recordings
    transcript_file = None
    recordings_dir = Path("recordings")
    if recordings_dir.exists():
        for file in recordings_dir.glob("*formatted_transcript.txt"):
            transcript_file = file
            break
    
    if transcript_file and transcript_file.exists():
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript_text = f.read()
    else:
        transcript_text = "Sample interview transcript - candidate discussed GenAI experience..."
    
    recording_id = db_ops.add_interview_recording(
        interview_id, "transcript",
        transcript_text=transcript_text,
        transcript_jsonl_path=str(transcript_file) if transcript_file else None,
        duration_seconds=3600
    )
    print(f"✅ Transcript added with ID: {recording_id}")
    
    # 7. Complete Interview
    print("\n7. Completing interview...")
    success = db_ops.update_interview_status(interview_id, "completed")
    print(f"✅ Interview completed")
    
    # 8. Generate Scoring Analysis
    print("\n8. Generating scoring analysis...")
    
    scoring_data = {
        "technical_skills_score": 8.0,
        "technical_skills_reasoning": "Strong GenAI and Python skills demonstrated",
        "problem_solving_score": 7.0,
        "problem_solving_reasoning": "Good problem-solving approach with room for improvement",
        "communication_score": 8.5,
        "communication_reasoning": "Excellent communication and articulation",
        "cultural_fit_score": 7.5,
        "cultural_fit_reasoning": "Good alignment with company values",
        "resume_match_score": 8.5,
        "interview_performance_score": 7.5,
        "overall_impression_score": 8.0,
        "overall_impression_reasoning": "Strong candidate with good potential",
        "key_strengths": ["Technical expertise", "Communication", "GenAI experience"],
        "areas_for_improvement": ["Problem-solving methodology", "DevOps skills"],
        "detailed_feedback": "Candidate demonstrates strong technical knowledge in GenAI and shows excellent communication skills. Recommended for hire with potential for growth.",
        "recommendation": "hire",
        "recommendation_reasoning": "Strong fit for the GenAI role with demonstrated experience"
    }
    
    analysis_id = db_ops.create_scoring_analysis(interview_id, scoring_data, "gemini-2.5-pro")
    print(f"✅ Scoring analysis created with ID: {analysis_id}")
    
    # 9. Generate Final Score
    print("\n9. Generating final score and decision...")
    
    final_score_id = db_ops.create_final_score(
        interview_id, 7.8, "hire",
        weighted_technical_score=8.0,
        weighted_behavioral_score=7.5,
        weighted_communication_score=8.5,
        weighted_cultural_fit_score=7.5,
        scoring_methodology="Weighted average: Technical (30%), Communication (25%), Problem-solving (25%), Cultural fit (20%)",
        confidence_level=0.87,
        decision_reasoning="Candidate exceeds technical requirements and demonstrates strong communication skills. Recommended for hire."
    )
    print(f"✅ Final score generated: 7.8/10 - HIRE decision")
    
    # 10. Get Complete Results
    print("\n10. Retrieving complete interview results...")
    
    full_results = db_ops.get_interview_full_results(interview_id)
    
    print(f"\n🎉 INTERVIEW SUMMARY:")
    print(f"   Candidate: {full_results['resume']['candidate_name']}")
    print(f"   Position: {full_results['job_description']['title']}")
    print(f"   Company: {full_results['job_description']['company']}")
    print(f"   Match Score: {full_results['match_rating']['overall_match_score']}%")
    print(f"   Final Score: {full_results['final_score']['final_score']}/10")
    print(f"   Decision: {full_results['final_score']['final_decision'].upper()}")
    print(f"   Confidence: {full_results['final_score']['confidence_level']*100:.1f}%")
    
    return interview_id

def example_integration_with_existing_files():
    """
    Example showing how to integrate existing recording files with database records.
    """
    print("\n=== Integration with Existing Files ===\n")
    
    db_ops = get_db_ops()
    
    # Process existing recording files
    recordings_dir = Path("recordings")
    
    if recordings_dir.exists():
        for transcript_file in recordings_dir.glob("*formatted_transcript.txt"):
            print(f"Processing: {transcript_file}")
            
            # Extract session ID from filename
            session_id = transcript_file.stem.replace("_formatted_transcript", "")
            
            # Check if interview exists
            interview = db_ops.get_interview_by_session(session_id)
            
            if interview:
                print(f"✅ Found existing interview for session: {session_id}")
                
                # Add transcript if not already added
                recordings = db_ops.get_interview_recordings(interview["id"])
                transcript_exists = any(r["recording_type"] == "transcript" for r in recordings)
                
                if not transcript_exists:
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcript_text = f.read()
                    
                    db_ops.add_interview_recording(
                        interview["id"], "transcript",
                        transcript_text=transcript_text,
                        formatted_transcript_path=str(transcript_file)
                    )
                    print(f"✅ Added transcript to interview")
                else:
                    print(f"ℹ️  Transcript already exists for this interview")
            else:
                print(f"⚠️  No interview found for session: {session_id}")
    
    # Process scoring files
    for score_file in recordings_dir.glob("*score.txt"):
        print(f"\nProcessing score file: {score_file}")
        
        session_id = score_file.stem.replace("_score", "")
        interview = db_ops.get_interview_by_session(session_id)
        
        if interview:
            with open(score_file, 'r', encoding='utf-8') as f:
                score_content = f.read()
            
            print(f"✅ Score content loaded for session: {session_id}")
            # You can parse this content and create scoring_analysis record
            # This would involve parsing the AI-generated evaluation
        else:
            print(f"⚠️  No interview found for score file: {score_file}")

def example_database_queries():
    """
    Example showing useful database queries for analytics and reporting.
    """
    print("\n=== Database Queries and Analytics ===\n")
    
    db_ops = get_db_ops()
    
    # Get recent interview statistics
    print("1. Recent Interview Statistics:")
    recent_interviews = db_ops.get_recent_interviews(30)  # Last 30 days
    
    if recent_interviews:
        total = len(recent_interviews)
        hired = len([i for i in recent_interviews if i.get('final_decision') == 'hire'])
        rejected = len([i for i in recent_interviews if i.get('final_decision') == 'reject'])
        
        print(f"   Total interviews: {total}")
        print(f"   Hired: {hired}")
        print(f"   Rejected: {rejected}")
        print(f"   Hire rate: {(hired/total)*100:.1f}%" if total > 0 else "   No data")
    else:
        print("   No recent interviews found")
    
    # Search functionality
    print("\n2. Candidate Search:")
    candidates = db_ops.search_candidates("Himanshu")
    print(f"   Found {len(candidates)} candidates matching 'Himanshu'")
    
    # Database statistics
    print("\n3. Database Statistics:")
    stats = db_ops.db_manager.get_database_stats()
    for key, value in stats.items():
        print(f"   {key.replace('_', ' ').title()}: {value}")

def main():
    """
    Main function demonstrating all examples.
    """
    print("SQLite Database Usage Examples for Live Interview App")
    print("=" * 60)
    
    # Run complete workflow example
    interview_id = example_complete_interview_workflow()
    
    # Show integration examples
    example_integration_with_existing_files()
    
    # Show query examples
    example_database_queries()
    
    print("\n" + "=" * 60)
    print("🎉 All examples completed successfully!")
    print("=" * 60)
    
    print("\nNext Steps:")
    print("1. Integrate database operations into your app.py and server.py")
    print("2. Update score_candidate.py to store results in database")
    print("3. Add database calls to your interview workflow")
    print("4. Use the database for analytics and reporting")

if __name__ == "__main__":
    main()
