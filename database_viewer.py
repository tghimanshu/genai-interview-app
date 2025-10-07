#!/usr/bin/env python3
"""
Simple database viewer for the Live Interview App
Provides a command-line interface to explore database contents
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from database_operations import get_db_ops

def print_separator(title: str = ""):
    """Print a formatted separator"""
    if title:
        print(f"\n{'='*20} {title} {'='*20}")
    else:
        print("="*60)

def print_table_data(data: List[Dict], title: str, max_rows: int = 10):
    """Print table data in a formatted way"""
    if not data:
        print(f"No {title.lower()} found.")
        return
    
    print(f"\n{title} ({len(data)} total, showing first {min(len(data), max_rows)}):")
    print("-" * 80)
    
    for i, item in enumerate(data[:max_rows]):
        print(f"{i+1}. ID: {item.get('id', 'N/A')}")
        
        # Show relevant fields based on data type
        if 'candidate_name' in item:
            print(f"   Name: {item.get('candidate_name', 'N/A')}")
            print(f"   Email: {item.get('email', 'N/A')}")
            print(f"   Experience: {item.get('experience_years', 'N/A')} years")
        
        elif 'title' in item and 'company' in item:
            print(f"   Title: {item.get('title', 'N/A')}")
            print(f"   Company: {item.get('company', 'N/A')}")
            print(f"   Location: {item.get('location', 'N/A')}")
        
        elif 'session_id' in item:
            print(f"   Session: {item.get('session_id', 'N/A')}")
            print(f"   Status: {item.get('status', 'N/A')}")
            print(f"   Duration: {item.get('duration_minutes', 'N/A')} minutes")
        
        elif 'overall_match_score' in item:
            print(f"   Match Score: {item.get('overall_match_score', 'N/A')}%")
            print(f"   Reasoning: {item.get('match_reasoning', 'N/A')[:100]}...")
        
        elif 'final_score' in item:
            print(f"   Final Score: {item.get('final_score', 'N/A')}/10")
            print(f"   Decision: {item.get('final_decision', 'N/A')}")
            print(f"   Confidence: {item.get('confidence_level', 'N/A')}")
        
        print(f"   Created: {item.get('created_at', 'N/A')}")
        print()

def view_database_overview():
    """Show database overview and statistics"""
    print_separator("DATABASE OVERVIEW")
    
    db_ops = get_db_ops()
    
    # Get statistics
    stats = db_ops.db_manager.get_database_stats()
    
    print("Database Statistics:")
    for key, value in stats.items():
        formatted_key = key.replace('_', ' ').title()
        print(f"  {formatted_key}: {value}")
    
    # Check database file
    db_path = Path("db/interview_database.db")
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"  Database File Size: {size_mb:.2f} MB")
        print(f"  Last Modified: {datetime.fromtimestamp(db_path.stat().st_mtime)}")

def view_job_descriptions():
    """View all job descriptions"""
    print_separator("JOB DESCRIPTIONS")
    
    db_ops = get_db_ops()
    jobs = db_ops.list_job_descriptions()
    print_table_data(jobs, "Job Descriptions")

def view_resumes():
    """View all resumes"""
    print_separator("CANDIDATE RESUMES")
    
    db_ops = get_db_ops()
    resumes = db_ops.list_resumes()
    print_table_data(resumes, "Resumes")

def view_interviews():
    """View all interviews"""
    print_separator("INTERVIEWS")
    
    db_ops = get_db_ops()
    query = "SELECT * FROM interview_summary ORDER BY created_at DESC"
    interviews = [dict(row) for row in db_ops.db_manager.execute_query(query)]
    
    if not interviews:
        print("No interviews found.")
        return
    
    print(f"Interviews ({len(interviews)} total):")
    print("-" * 100)
    
    for i, interview in enumerate(interviews[:10]):
        print(f"{i+1}. Interview ID: {interview.get('interview_id', 'N/A')}")
        print(f"   Session: {interview.get('session_id', 'N/A')}")
        print(f"   Candidate: {interview.get('candidate_name', 'N/A')}")
        print(f"   Job: {interview.get('job_title', 'N/A')} at {interview.get('company', 'N/A')}")
        print(f"   Status: {interview.get('status', 'N/A')}")
        print(f"   Match Score: {interview.get('overall_match_score', 'N/A')}%")
        print(f"   Final Score: {interview.get('final_score', 'N/A')}/10")
        print(f"   Decision: {interview.get('final_decision', 'N/A')}")
        print(f"   Duration: {interview.get('duration_minutes', 'N/A')} minutes")
        print(f"   Date: {interview.get('started_at', interview.get('created_at', 'N/A'))}")
        print()

def view_detailed_interview(interview_id: int):
    """View detailed interview results"""
    print_separator(f"INTERVIEW DETAILS - ID: {interview_id}")
    
    db_ops = get_db_ops()
    results = db_ops.get_interview_full_results(interview_id)
    
    if not results:
        print(f"No interview found with ID: {interview_id}")
        return
    
    # Basic interview info
    interview = results.get('interview', {})
    job = results.get('job_description', {})
    resume = results.get('resume', {})
    match_rating = results.get('match_rating', {})
    scoring = results.get('scoring_analysis', {})
    final_score = results.get('final_score', {})
    
    print("BASIC INFORMATION:")
    print(f"  Session ID: {interview.get('session_id', 'N/A')}")
    print(f"  Status: {interview.get('status', 'N/A')}")
    print(f"  Duration: {interview.get('duration_minutes', 'N/A')} minutes")
    print(f"  Started: {interview.get('started_at', 'N/A')}")
    print(f"  Ended: {interview.get('ended_at', 'N/A')}")
    
    print("\nCANDIDATE:")
    print(f"  Name: {resume.get('candidate_name', 'N/A')}")
    print(f"  Email: {resume.get('email', 'N/A')}")
    print(f"  Experience: {resume.get('experience_years', 'N/A')} years")
    print(f"  Education: {resume.get('education', 'N/A')}")
    
    print("\nPOSITION:")
    print(f"  Title: {job.get('title', 'N/A')}")
    print(f"  Company: {job.get('company', 'N/A')}")
    print(f"  Location: {job.get('location', 'N/A')}")
    print(f"  Salary Range: {job.get('salary_range', 'N/A')}")
    
    print("\nMATCH RATING:")
    print(f"  Overall Match: {match_rating.get('overall_match_score', 'N/A')}%")
    print(f"  Reasoning: {match_rating.get('match_reasoning', 'N/A')}")
    
    if scoring:
        print("\nSCORING ANALYSIS:")
        print(f"  Technical Skills: {scoring.get('technical_skills_score', 'N/A')}/10")
        print(f"  Problem Solving: {scoring.get('problem_solving_score', 'N/A')}/10")
        print(f"  Communication: {scoring.get('communication_score', 'N/A')}/10")
        print(f"  Cultural Fit: {scoring.get('cultural_fit_score', 'N/A')}/10")
        print(f"  Resume Match: {scoring.get('resume_match_score', 'N/A')}/10")
        print(f"  Interview Performance: {scoring.get('interview_performance_score', 'N/A')}/10")
        print(f"  Recommendation: {scoring.get('recommendation', 'N/A')}")
        
        # Key strengths
        strengths = scoring.get('key_strengths')
        if strengths:
            try:
                strengths_list = json.loads(strengths) if isinstance(strengths, str) else strengths
                print(f"  Key Strengths: {', '.join(strengths_list[:3])}")
            except:
                print(f"  Key Strengths: {strengths}")
        
        # Areas for improvement
        improvements = scoring.get('areas_for_improvement')
        if improvements:
            try:
                improvements_list = json.loads(improvements) if isinstance(improvements, str) else improvements
                print(f"  Areas for Improvement: {', '.join(improvements_list[:3])}")
            except:
                print(f"  Areas for Improvement: {improvements}")
    
    if final_score:
        print("\nFINAL DECISION:")
        print(f"  Final Score: {final_score.get('final_score', 'N/A')}/10")
        print(f"  Decision: {final_score.get('final_decision', 'N/A').upper()}")
        print(f"  Pass/Fail: {final_score.get('pass_fail_status', 'N/A')}")
        print(f"  Confidence: {final_score.get('confidence_level', 'N/A')}")
        print(f"  Reasoning: {final_score.get('decision_reasoning', 'N/A')}")
    
    # Show recordings
    recordings = results.get('recordings', [])
    if recordings:
        print(f"\nRECORDINGS ({len(recordings)}):")
        for rec in recordings:
            print(f"  - {rec.get('recording_type', 'N/A')}: {rec.get('file_path', 'N/A')}")

def search_interviews():
    """Search interviews by candidate name"""
    candidate_name = input("Enter candidate name to search: ").strip()
    if not candidate_name:
        return
    
    print_separator(f"SEARCH RESULTS: '{candidate_name}'")
    
    db_ops = get_db_ops()
    candidates = db_ops.search_candidates(candidate_name)
    
    if not candidates:
        print(f"No candidates found matching '{candidate_name}'")
        return
    
    print(f"Found {len(candidates)} candidates:")
    for candidate in candidates:
        print(f"  - {candidate.get('candidate_name', 'N/A')} ({candidate.get('email', 'N/A')})")
        
        # Find interviews for this candidate
        query = """
        SELECT i.id, i.session_id, i.status, fs.final_score, fs.final_decision
        FROM interviews i
        LEFT JOIN final_scores fs ON i.id = fs.interview_id
        WHERE i.resume_id = ?
        ORDER BY i.created_at DESC
        """
        interviews = db_ops.db_manager.execute_query(query, (candidate['id'],))
        
        if interviews:
            print(f"    Interviews ({len(interviews)}):")
            for interview in interviews:
                score = interview[3] if interview[3] else "N/A"
                decision = interview[4] if interview[4] else "N/A"
                print(f"      • ID {interview[0]}: {interview[2]} - Score: {score}/10 - Decision: {decision}")
        else:
            print("    No interviews found")
        print()

def main_menu():
    """Display main menu and handle user choices"""
    while True:
        print_separator("LIVE INTERVIEW DATABASE VIEWER")
        print("1. Database Overview")
        print("2. View Job Descriptions") 
        print("3. View Candidate Resumes")
        print("4. View All Interviews")
        print("5. View Detailed Interview (by ID)")
        print("6. Search Interviews by Candidate")
        print("7. Exit")
        
        choice = input("\nSelect an option (1-7): ").strip()
        
        try:
            if choice == '1':
                view_database_overview()
            elif choice == '2':
                view_job_descriptions()
            elif choice == '3':
                view_resumes()
            elif choice == '4':
                view_interviews()
            elif choice == '5':
                interview_id = input("Enter interview ID: ").strip()
                if interview_id.isdigit():
                    view_detailed_interview(int(interview_id))
                else:
                    print("Invalid interview ID")
            elif choice == '6':
                search_interviews()
            elif choice == '7':
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please select 1-7.")
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    # Check if database exists
    db_path = Path("db/interview_database.db")
    if not db_path.exists():
        print("❌ Database not found: db/interview_database.db")
        print("Please run 'python init_database.py' first to create the database.")
        exit(1)
    
    print("Welcome to the Live Interview Database Viewer!")
    main_menu()