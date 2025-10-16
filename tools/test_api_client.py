"""
In-process API integration tests using FastAPI TestClient.
This will override the server's InterviewDatabaseOps factory to use a test DB
`db/test_interview_database.db`, create the schema, then exercise endpoints.
"""

from fastapi.testclient import TestClient
import os
import json
import time

import init_database
import database_operations
import server

TEST_DB = "db/test_interview_database.db"

# Ensure test DB is created fresh
db_mgr = init_database.DatabaseManager(TEST_DB)
if os.path.exists(TEST_DB):
    try:
        os.remove(TEST_DB)
    except Exception:
        pass
created = db_mgr.create_database(force_recreate=True)
if not created:
    print("Failed to create test database")
    raise SystemExit(1)

# Override the InterviewDatabaseOps used by server endpoints to point to test DB
server.InterviewDatabaseOps = lambda *a, **k: database_operations.InterviewDatabaseOps(TEST_DB)

client = TestClient(server.app)

def pretty(resp):
    try:
        return json.dumps(resp.json(), indent=2)
    except Exception:
        return resp.text


def run():
    print("Running in-process API tests against TestClient")

    r = client.get("/health")
    print("/health", r.status_code, r.json())
    assert r.status_code == 200 and r.json().get("status") == "ok"

    job_payload = {
        "title": "Test Job - InProcess",
        "company": "TestCorp",
        "description_text": "Integration test job",
    }
    r = client.post("/api/jobs", json=job_payload)
    print("POST /api/jobs", r.status_code)
    print(pretty(r))
    assert r.status_code == 200
    job_id = r.json().get("id")

    resume_payload = {
        "candidate_name": "InProcess Candidate",
        "email": "inprocess@example.com",
        "resume_text": "Test resume",
    }
    r = client.post("/api/resumes", json=resume_payload)
    print("POST /api/resumes", r.status_code)
    print(pretty(r))
    assert r.status_code == 200
    resume_id = r.json().get("id")

    interview_payload = {
        "job_description_id": job_id,
        "resume_id": resume_id,
        "session_id": "inprocess_session",
    }
    r = client.post("/api/interviews", json=interview_payload)
    print("POST /api/interviews", r.status_code)
    print(pretty(r))
    assert r.status_code == 200
    interview_id = r.json().get("id")

    rating_payload = {
        "job_description_id": job_id,
        "resume_id": resume_id,
        "overall_score": 80.0,
        "reasoning": "Automated in-process test",
    }
    r = client.post("/api/match-rating", json=rating_payload)
    print("POST /api/match-rating", r.status_code)
    print(pretty(r))
    assert r.status_code == 200

    r = client.get(f"/api/interviews/{interview_id}")
    print(f"GET /api/interviews/{interview_id}", r.status_code)
    print(pretty(r))
    assert r.status_code == 200

    # Soft-delete
    r = client.delete(f"/api/jobs/{job_id}")
    print(f"DELETE /api/jobs/{job_id}", r.status_code)
    assert r.status_code == 200

    r = client.delete(f"/api/resumes/{resume_id}")
    print(f"DELETE /api/resumes/{resume_id}", r.status_code)
    assert r.status_code == 200

    print("All in-process API integration tests passed")


if __name__ == '__main__':
    run()
