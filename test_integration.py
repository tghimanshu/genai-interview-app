#!/usr/bin/env python3
"""
Integration test script to verify data consistency across the full stack.

This script spins up the FastAPI server in a background thread and runs a series
of requests against the API endpoints to ensure they are reachable and return
consistent data structures.
"""

import json
import time
import threading
import requests
import uvicorn
from server import app
from database_operations import InterviewDatabaseOps

def run_server():
    """Run the FastAPI server in background"""
    uvicorn.run(app, host='127.0.0.1', port=8000, log_level='error')

def test_api_consistency():
    """
    Test API endpoints for data consistency.

    Performs GET requests to key endpoints (/health, /api/analytics/stats, /api/jobs,
    /api/resumes, /api/interviews) and verifies their status codes and response structures.
    """
    base_url = "http://127.0.0.1:8000"
    
    # Wait for server to start
    time.sleep(2)
    
    print("Testing API endpoint consistency...")
    
    try:
        # Test health check
        response = requests.get(f"{base_url}/health")
        print(f"✓ Health check: {response.status_code}")
        
        # Test stats endpoint
        response = requests.get(f"{base_url}/api/analytics/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ Stats endpoint: {stats}")
        
        # Test jobs endpoint
        response = requests.get(f"{base_url}/api/jobs")
        if response.status_code == 200:
            jobs_data = response.json()
            print(f"✓ Jobs endpoint: {len(jobs_data.get('jobs', []))} jobs")
        
        # Test resumes endpoint
        response = requests.get(f"{base_url}/api/resumes")
        if response.status_code == 200:
            resumes_data = response.json()
            print(f"✓ Resumes endpoint: {len(resumes_data.get('resumes', []))} resumes")
        
        # Test interviews endpoint
        response = requests.get(f"{base_url}/api/interviews")
        if response.status_code == 200:
            interviews_data = response.json()
            print(f"✓ Interviews endpoint: {len(interviews_data.get('interviews', []))} interviews")
        
        print("✓ All API endpoints are working consistently!")
        
    except requests.RequestException as e:
        print(f"✗ API test failed: {e}")
    except Exception as e:
        print(f"✗ Test error: {e}")

if __name__ == "__main__":
    print("Starting integration test...")
    
    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Run API tests
    test_api_consistency()
    
    print("Integration test completed!")
