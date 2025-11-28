"""
Simple API integration test simulating UI flows against the backend.

This script performs a sequence of HTTP requests to a running backend server to
verify the core business logic. It covers:
- Health check
- CRUD operations for jobs and resumes
- Interview creation
- Match rating generation
- Fetching full interview results
- Cleanup (soft deletion)

Prerequisites:
- The backend server must be running at http://127.0.0.1:8000.
"""

import requests
import time
import json

BASE = "http://127.0.0.1:8000"

results = []

def check_health():
    """
    Check if the backend server is healthy.

    Returns:
        bool: True if the server returns 200 OK and status='ok', False otherwise.
    """
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception as e:
        print("Health check failed:", e)
        return False


def pretty(r):
    """
    Format response JSON for pretty printing.

    Args:
        r (requests.Response): The response object.

    Returns:
        str: Pretty-printed JSON string or raw text if parsing fails.
    """
    try:
        return json.dumps(r.json(), indent=2)
    except Exception:
        return r.text


def run_tests():
    """
    Run the integration test suite.

    Steps:
    1. Health check.
    2. Create a test job.
    3. Create a test resume.
    4. Create an interview linking job and resume.
    5. Create a match rating.
    6. Fetch full interview details.
    7. Clean up (delete job and resume).

    Returns:
        int: 0 on success, non-zero error code on failure.
    """
    print("Starting API integration tests against", BASE)
    if not check_health():
        print("Backend health check failed. Make sure the server is running at", BASE)
        return 1

    # Test job create
    job_payload = {
        "title": "Test Job - API Integration",
        "company": "TestCorp",
        "description_text": "This is a test job created by integration test",
        "requirements": "None",
    }
    r = requests.post(f"{BASE}/api/jobs", json=job_payload, timeout=10)
    print("Create job ->", r.status_code)
    print(pretty(r))
    if r.status_code != 200:
        return 2
    job_id = r.json().get("id")

    # Test resume create
    resume_payload = {
        "candidate_name": "Test Candidate",
        "email": "test.candidate@example.com",
        "resume_text": "This is a test resume",
    }
    r = requests.post(f"{BASE}/api/resumes", json=resume_payload, timeout=10)
    print("Create resume ->", r.status_code)
    print(pretty(r))
    if r.status_code != 200:
        return 3
    resume_id = r.json().get("id")

    # Test create interview
    interview_payload = {
        "job_description_id": job_id,
        "resume_id": resume_id,
        "session_id": "test_session_1",
    }
    r = requests.post(f"{BASE}/api/interviews", json=interview_payload, timeout=10)
    print("Create interview ->", r.status_code)
    print(pretty(r))
    if r.status_code != 200:
        return 4
    interview_id = r.json().get("id")

    # Create match rating
    rating_payload = {
        "job_description_id": job_id,
        "resume_id": resume_id,
        "overall_score": 75.0,
        "reasoning": "Automated test rating",
    }
    r = requests.post(f"{BASE}/api/match-rating", json=rating_payload, timeout=10)
    print("Create match rating ->", r.status_code)
    print(pretty(r))
    if r.status_code != 200:
        return 5

    # Create scoring analysis via direct DB ops endpoint isn't available; skip heavy AI scoring.

    # Fetch full interview results
    r = requests.get(f"{BASE}/api/interviews/{interview_id}", timeout=10)
    print("Get interview full results ->", r.status_code)
    print(pretty(r))
    if r.status_code != 200:
        return 6

    # Cleanup: soft-delete job and resume
    r = requests.delete(f"{BASE}/api/jobs/{job_id}", timeout=10)
    print("Delete job ->", r.status_code)
    print(pretty(r))

    r = requests.delete(f"{BASE}/api/resumes/{resume_id}", timeout=10)
    print("Delete resume ->", r.status_code)
    print(pretty(r))

    print("Integration tests finished successfully")
    return 0


if __name__ == '__main__':
    exit(run_tests())
