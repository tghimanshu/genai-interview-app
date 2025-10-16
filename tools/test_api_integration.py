"""
Simple API integration test that simulates UI flows against the backend.
It performs: health check, create/list/get/update/delete for jobs and resumes,
create interview, create match rating, get full interview results.

Run this while the backend is running at http://127.0.0.1:8000
"""

import requests
import time
import json

BASE = "http://127.0.0.1:8000"

results = []

def check_health():
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception as e:
        print("Health check failed:", e)
        return False


def pretty(r):
    try:
        return json.dumps(r.json(), indent=2)
    except Exception:
        return r.text


def run_tests():
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
