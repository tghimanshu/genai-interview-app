#!/usr/bin/env python3
"""Start the FastAPI server"""
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