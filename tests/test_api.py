import os
import json
import tempfile
import shutil
import pytest

from fastapi.testclient import TestClient

from db import init_database
from db import database_operations
import server


@pytest.fixture(scope="module")
def test_db_dir(tmp_path_factory):
    td = tmp_path_factory.mktemp("dbtest")
    db_path = str(td / "test_interview_database.db")
    # create database
    mgr = init_database.DatabaseManager(db_path)
    assert mgr.create_database(force_recreate=True)
    yield db_path
    # teardown
    try:
        os.remove(db_path)
    except Exception:
        pass


@pytest.fixture(scope="module")
def client(test_db_dir):
    # Ensure server uses test DB
    server.InterviewDatabaseOps = (
        lambda *a, **k: database_operations.InterviewDatabaseOps(test_db_dir)
    )
    # The server module sets DATABASE_AVAILABLE at import time; tests should enable it
    server.DATABASE_AVAILABLE = True
    client = TestClient(server.app)
    yield client


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_crud_job_resume_interview_flow(client):
    # create job
    job_payload = {"title": "PyTest Job", "company": "CI", "description_text": "desc"}
    r = client.post("/api/jobs", json=job_payload)
    assert r.status_code == 200
    job_id = r.json().get("id")

    # create resume
    resume_payload = {"candidate_name": "PyTest", "resume_text": "resume"}
    r = client.post("/api/resumes", json=resume_payload)
    assert r.status_code == 200
    resume_id = r.json().get("id")

    # create interview
    interview_payload = {
        "job_description_id": job_id,
        "resume_id": resume_id,
        "session_id": "pytest_session",
    }
    r = client.post("/api/interviews", json=interview_payload)
    assert r.status_code == 200
    interview_id = r.json().get("id")

    # create match rating
    rating_payload = {
        "job_description_id": job_id,
        "resume_id": resume_id,
        "overall_score": 80.0,
        "reasoning": "ok",
    }
    r = client.post("/api/match-rating", json=rating_payload)
    assert r.status_code == 200

    # fetch full results
    r = client.get(f"/api/interviews/{interview_id}")
    assert r.status_code == 200
    data = r.json()
    assert data.get("interview") and data.get("job_description") and data.get("resume")

    # cleanup soft deletes
    r = client.delete(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    r = client.delete(f"/api/resumes/{resume_id}")
    assert r.status_code == 200
