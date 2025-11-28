#!/usr/bin/env python3
"""
Updated score_candidate.py with database integration.

This version saves scoring results to the SQLite database. It parses the AI's
response to extract numerical scores and structured feedback, then stores it
using the `InterviewDatabaseOps` class.
"""

from google import genai
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from google.genai import types
from dotenv import load_dotenv

from database_operations import get_db_ops, JobDescription, Resume, Interview

load_dotenv()

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY", "<Enter your API key here>"),
)

def parse_scoring_response(response_text: str) -> Dict[str, Any]:
    """
    Parse AI response and extract structured scoring data.

    Uses regex patterns to find scores for various criteria within the unstructured
    text response from the AI model.

    Args:
        response_text (str): The raw text response from the AI.

    Returns:
        Dict[str, Any]: A dictionary containing extracted scores, reasoning, and lists.
    """
    scoring_data = {
        "technical_skills_score": None,
        "technical_skills_reasoning": "",
        "problem_solving_score": None,
        "problem_solving_reasoning": "",
        "communication_score": None,
        "communication_reasoning": "",
        "cultural_fit_score": None,
        "cultural_fit_reasoning": "",
        "resume_match_score": None,
        "interview_performance_score": None,
        "overall_impression_score": None,
        "overall_impression_reasoning": "",
        "detailed_feedback": response_text,
        "recommendation": "pending",
        "recommendation_reasoning": "",
        "key_strengths": [],
        "areas_for_improvement": []
    }
    
    # Extract numerical scores using regex patterns
    score_patterns = {
        "technical_skills_score": r"technical.*?(\d+(?:\.\d+)?)/10",
        "problem_solving_score": r"problem[\s\-]*solving.*?(\d+(?:\.\d+)?)/10",
        "communication_score": r"communication.*?(\d+(?:\.\d+)?)/10",
        "cultural_fit_score": r"cultural.*?fit.*?(\d+(?:\.\d+)?)/10",
        "overall_impression_score": r"overall.*?(\d+(?:\.\d+)?)/10",
        "resume_match_score": r"resume.*?match.*?(\d+(?:\.\d+)?)/10",
        "interview_performance_score": r"interview.*?performance.*?(\d+(?:\.\d+)?)/10"
    }
    
    text_lower = response_text.lower()
    
    for key, pattern in score_patterns.items():
        match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                scoring_data[key] = float(match.group(1))
            except (ValueError, AttributeError):
                pass
    
    # Extract final score
    final_score_match = re.search(r"final.*?score.*?(\d+(?:\.\d+)?)/10", text_lower)
    if final_score_match:
        scoring_data["final_score"] = float(final_score_match.group(1))
    else:
        # Calculate weighted average if final score not found
        scores = [v for k, v in scoring_data.items() if k.endswith("_score") and v is not None]
        if scores:
            scoring_data["final_score"] = sum(scores) / len(scores)
    
    # Extract recommendation
    if any(word in text_lower for word in ["recommend", "hire", "accept"]):
        if any(word in text_lower for word in ["reject", "not recommend", "decline"]):
            scoring_data["recommendation"] = "reject"
        else:
            scoring_data["recommendation"] = "hire"
    elif any(word in text_lower for word in ["maybe", "second interview", "further"]):
        scoring_data["recommendation"] = "second_interview"
    
    # Extract key strengths and areas for improvement
    strengths_section = re.search(r"strengths?[:\-\s]*(.*?)(?=areas?\s+for\s+improvement|weaknesses?|cons?:|$)", 
                                 response_text, re.IGNORECASE | re.DOTALL)
    if strengths_section:
        strengths_text = strengths_section.group(1)
        # Extract bullet points or numbered items
        strengths = re.findall(r"[•\-\*\d+\.\s]*([^•\-\*\n]+)", strengths_text)
        scoring_data["key_strengths"] = [s.strip() for s in strengths if s.strip()][:5]
    
    improvements_section = re.search(r"(?:areas?\s+for\s+improvement|weaknesses?|cons?:)[:\-\s]*(.*?)(?=\n\n|$)", 
                                   response_text, re.IGNORECASE | re.DOTALL)
    if improvements_section:
        improvements_text = improvements_section.group(1)
        improvements = re.findall(r"[•\-\*\d+\.\s]*([^•\-\*\n]+)", improvements_text)
        scoring_data["areas_for_improvement"] = [i.strip() for i in improvements if i.strip()][:5]
    
    return scoring_data

def get_or_create_interview_data(session_id: str) -> Optional[int]:
    """
    Get existing interview data or create if needed.

    If the session ID corresponds to an existing interview, returns its ID.
    Otherwise, attempts to create a new job description and resume from local files,
    then creates a new interview record.

    Args:
        session_id (str): The session ID.

    Returns:
        Optional[int]: The interview ID if successful, None otherwise.
    """
    db_ops = get_db_ops()
    
    # Try to find existing interview by session_id
    interview = db_ops.get_interview_by_session(session_id)
    if interview:
        return interview["id"]
    
    # If not found, we need to create job description and resume first
    print(f"No existing interview found for session {session_id}")
    print("Creating job description and resume from files...")
    
    # Create job description from file
    jd_file = Path("SDE_JD.txt")
    if jd_file.exists():
        with open(jd_file, 'r', encoding='utf-8') as f:
            jd_text = f.read()
        
        job_desc = JobDescription(
            title="Software Development Engineer - GenAI",
            company="Interview Company",
            description_text=jd_text,
            requirements="Requirements from JD file",
            skills_required=json.dumps(["Python", "GenAI", "Machine Learning", "Vertex AI"])
        )
        job_id = db_ops.create_job_description(job_desc)
        print(f"Created job description with ID: {job_id}")
    else:
        print("⚠️  SDE_JD.txt not found - please create job description manually")
        return None
    
    # Create resume from file
    resume_file = Path("himanshu-resume.txt")
    if resume_file.exists():
        with open(resume_file, 'r', encoding='utf-8') as f:
            resume_text = f.read()
        
        resume = Resume(
            candidate_name="Himanshu Gohil",
            email="himanshu.gohil@example.com",
            resume_text=resume_text,
            resume_pdf_path="himanshu-resume.pdf",
            skills=json.dumps(["Python", "GenAI", "Vertex AI", "Google Cloud"])
        )
        resume_id = db_ops.create_resume(resume)
        print(f"Created resume with ID: {resume_id}")
    else:
        print("⚠️  himanshu-resume.txt not found - please create resume manually")
        return None
    
    # Create interview
    interview = Interview(
        session_id=session_id,
        job_description_id=job_id,
        resume_id=resume_id,
        status="completed"  # Since we're scoring, it's already completed
    )
    interview_id = db_ops.create_interview(interview)
    print(f"Created interview with ID: {interview_id}")
    
    return interview_id

def score_candidate_with_database(session_id: Optional[str] = None, 
                                transcript_file: str = "final_transcription.txt") -> bool:
    """
    Score candidate and save results to database.

    Args:
        session_id (Optional[str]): Interview session ID. If None, extracted from filename.
        transcript_file (str): Name of transcript file.

    Returns:
        bool: True if successful, False otherwise.
    """
    
    # Extract session_id from transcript filename if not provided
    if not session_id:
        transcript_path = Path(transcript_file)
        if "session_" in transcript_path.stem:
            session_id = transcript_path.stem.split("_")[0] + "_" + transcript_path.stem.split("_")[1] + "_" + transcript_path.stem.split("_")[2]
        else:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"Scoring interview session: {session_id}")
    
    # Check if required files exist
    required_files = [transcript_file, "himanshu-resume.txt", "SDE_JD.txt"]
    missing_files = [f for f in required_files if not Path(f).exists()]
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    
    try:
        # Initialize database operations
        db_ops = get_db_ops()
        
        # Get or create interview record
        interview_id = get_or_create_interview_data(session_id)
        if not interview_id:
            print("❌ Failed to get or create interview data")
            return False
        
        print(f"Using interview ID: {interview_id}")
        
        # Generate AI scoring (existing logic)
        print("Generating AI scoring analysis...")
        
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents={
                "role": "user",
                "parts": [
                    types.Part.from_bytes(
                        mime_type="text/plain",
                        data=open(transcript_file, "rb").read()
                    ),
                    types.Part.from_bytes(
                        mime_type="text/plain",
                        data=open("himanshu-resume.txt", "rb").read()
                    ),
                    types.Part.from_bytes(
                        mime_type="text/plain",
                        data=open("SDE_JD.txt", "rb").read()
                    ),
                    types.Part.from_text(
                        text="""
Score the candidate based on the following criteria:
1. Technical Skills: Evaluate the candidate's proficiency in relevant technical skills and knowledge.
2. Problem-Solving Ability: Assess the candidate's ability to analyze and solve problems effectively
3. Communication Skills: Rate the candidate's ability to communicate ideas clearly and effectively.
4. Cultural Fit: Determine how well the candidate aligns with the company's values and culture.
5. Overall Impression: Provide an overall score based on the candidate's performance during the interview.

Give reasonings and key takeaways for each criteria. Provide a final score out of 10.
Give Scores for resume match and interview performance separately and then take an average of both to give final score out of 10.

Format your response with clear sections and numerical scores out of 10 for each criteria.
"""
                    )
                ]
            }
        )
        
        print("✅ AI scoring completed")
        
        # Save original response to file (backward compatibility)
        output_file = f"recordings/{session_id}_score.txt" if Path("recordings").exists() else "final_evaluation.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"✅ Score saved to {output_file}")
        
        # Parse structured scoring data
        scoring_data = parse_scoring_response(response.text)
        
        # Save to database
        print("Saving scoring analysis to database...")
        analysis_id = db_ops.create_scoring_analysis(
            interview_id, scoring_data, "gemini-2.5-pro"
        )
        
        if analysis_id:
            print(f"✅ Scoring analysis saved with ID: {analysis_id}")
        else:
            print("❌ Failed to save scoring analysis")
            return False
        
        # Save final score
        final_score = scoring_data.get("final_score", 5.0)
        recommendation = scoring_data.get("recommendation", "pending")
        
        final_score_id = db_ops.create_final_score(
            interview_id, final_score, recommendation,
            scoring_methodology="AI-generated evaluation using gemini-2.5-pro",
            confidence_level=0.8,  # Default confidence
            decision_reasoning=scoring_data.get("recommendation_reasoning", "Based on comprehensive AI analysis")
        )
        
        if final_score_id:
            print(f"✅ Final score saved with ID: {final_score_id}")
        else:
            print("❌ Failed to save final score")
            return False
        
        # Add transcript to database if not already added
        recordings = db_ops.get_interview_recordings(interview_id)
        transcript_exists = any(r["recording_type"] == "transcript" for r in recordings)
        
        if not transcript_exists:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
            
            recording_id = db_ops.add_interview_recording(
                interview_id, "transcript",
                transcript_text=transcript_text,
                formatted_transcript_path=transcript_file
            )
            print(f"✅ Transcript saved with ID: {recording_id}")
        
        # Display summary
        print("\n" + "="*60)
        print("🎉 SCORING SUMMARY")
        print("="*60)
        print(f"Session ID: {session_id}")
        print(f"Interview ID: {interview_id}")
        print(f"Final Score: {final_score:.1f}/10")
        print(f"Recommendation: {recommendation.upper()}")
        print(f"Technical Score: {scoring_data.get('technical_skills_score', 'N/A')}")
        print(f"Communication Score: {scoring_data.get('communication_score', 'N/A')}")
        print(f"Problem Solving: {scoring_data.get('problem_solving_score', 'N/A')}")
        
        if scoring_data.get("key_strengths"):
            print(f"Key Strengths: {', '.join(scoring_data['key_strengths'][:3])}")
        
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during scoring: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function - updated version of original score_candidate.py"""
    
    print("AI Interview Scoring with Database Integration")
    print("=" * 50)
    
    # Check for existing recording files
    recordings_dir = Path("recordings")
    transcript_files = []
    
    if recordings_dir.exists():
        transcript_files = list(recordings_dir.glob("*formatted_transcript.txt"))
    
    if transcript_files:
        print(f"Found {len(transcript_files)} transcript files:")
        for i, file in enumerate(transcript_files):
            print(f"  {i+1}. {file.name}")
        
        try:
            choice = input(f"\nSelect file (1-{len(transcript_files)}) or press Enter for latest: ").strip()
            if choice:
                selected_file = transcript_files[int(choice)-1]
            else:
                selected_file = max(transcript_files, key=lambda f: f.stat().st_mtime)
            
            # Extract session ID from filename
            session_id = selected_file.stem.replace("_formatted_transcript", "")
            
            print(f"Processing: {selected_file}")
            success = score_candidate_with_database(session_id, str(selected_file))
            
        except (ValueError, IndexError, KeyboardInterrupt):
            print("Invalid selection or cancelled")
            return
    
    else:
        # Use default files (backward compatibility)
        print("No transcript files found in recordings/, using default files...")
        success = score_candidate_with_database()
    
    if success:
        print("\n✅ Scoring completed successfully!")
        print("You can now view results in the database or use the web interface.")
    else:
        print("\n❌ Scoring failed!")

if __name__ == "__main__":
    main()
