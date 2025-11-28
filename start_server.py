#!/usr/bin/env python3
"""
Start the FastAPI server.

This script initializes and runs the Uvicorn server to serve the FastAPI application
defined in `server.py`. It is the entry point for running the backend service.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        # Disable reload for stable test runs; use reload=True only during active development.
        reload=False,
        log_level="info"
    )
