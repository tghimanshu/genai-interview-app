# Interview App

GenAI-powered live interview assistant that now supports browser-based participation via a Vite + React client communicating with the Gemini Live API through a WebSocket bridge.

## Prerequisites

- Python 3.9+
- Node.js 18+
- A valid `GEMINI_API_KEY` in your environment (place in `.env`)

## Backend setup

Install Python dependencies and launch the FastAPI server (uses uvicorn):

```bash
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

The backend exposes a WebSocket endpoint at `ws://localhost:8000/ws/interview` and a health probe at `http://localhost:8000/health`.

### Session resumption & recordings

- Every live session receives a **resume handle** that the frontend stores in `localStorage`. If the browser disconnects unexpectedly, the client automatically attempts to reconnect (up to 5 backoff retries) using that handle so the interview can continue without losing context.
- You can also reconnect manually by loading the app and pressing **Connect**; the existing handle is appended to the WebSocket URL. Use the **Clear stored handle** button in the UI (when disconnected) to force a fresh interview.
- The backend persistently captures raw audio streams for both parties in the `recordings/` folder:
  - `session_<timestamp>_assistant.wav`
  - `session_<timestamp>_candidate.wav`
  - `session_<timestamp>_mix.wav` (simple blended track)
  - `session_<timestamp>_transcripts.jsonl` (newline-delimited JSON with UTC timestamps, role, and text payload)
- Once the interviewer delivers the final sign-off (or the look-away limit is reached), the session is closed automatically, the browser is notified, and the stored resume handle is cleared so the next connection starts a fresh interview.

Recordings are written when the session ends or the socket closes. Ensure the process has write permissions to the project directory.

## Frontend (Vite + React)

Install dependencies and run the dev server:

```bash
cd webclient
npm install
npm run dev
```

Optionally create a `.env` file in `webclient/` to override the WebSocket URL:

```
VITE_WS_URL=ws://localhost:8000/ws/interview
```

The Vite dev server runs on `http://localhost:5173` by default. Open it in the browser, connect to the backend, and allow microphone (and optionally camera) access to start the interview.

## Legacy CLI runner

The original CLI client remains available for diagnostics:

```bash
python app.py --mode none
```
