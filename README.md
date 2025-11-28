# Live Interview App

A comprehensive AI-powered interview platform designed to conduct live, structured technical interviews. The system leverages the Gemini Live API for real-time audio/video interaction, analyzes candidate performance, and provides detailed scoring and feedback.

## Features

- **Live Interview Engine**: Real-time audio/video interaction using Gemini Live API via WebSocket/WebRTC.
- **Backend API**: Robust FastAPI server managing job descriptions, resumes, interviews, and recordings.
- **Database Integration**: SQLite database for persistent storage of all interview data.
- **Automated Scoring**: Post-interview analysis generating scores for technical skills, communication, and cultural fit.
- **Resume Parsing**: Extraction of text and details from uploaded resumes.
- **Proctoring**: Basic face tracking to monitor candidate attention (look-away detection).
- **Session Management**: Resume capability for interrupted sessions and audio recording/archiving.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for the frontend)
- **FFmpeg**: Required for audio processing and MP3 export.
    - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin` folder to your PATH.
    - **Linux**: `sudo apt-get install ffmpeg`
    - **macOS**: `brew install ffmpeg`
- **PortAudio**: Required for microphone access (`pyaudio`).
    - **Linux**: `sudo apt-get install portaudio19-dev`
    - **macOS**: `brew install portaudio`
- A valid **Google GenAI API Key** (`GEMINI_API_KEY`).

## Setup

### 1. Backend Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Create a virtual environment** (recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If `requirements.txt` is missing, install core packages manually:*
    ```bash
    pip install google-genai opencv-python pyaudio pillow mss pydub fastapi uvicorn requests python-dotenv aiortc
    ```

4.  **Configure Environment Variables**:
    Create a `.env` file in the root directory and add your API key and email configuration (optional):
    ```env
    GEMINI_API_KEY=your_gemini_api_key_here
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=465
    SMTP_USERNAME=your_email@gmail.com
    SMTP_PASSWORD=your_app_password
    ```

5.  **Initialize the Database**:
    Run the initialization script to create the SQLite database schema:
    ```bash
    python init_database.py
    ```

### 2. Frontend Setup

1.  Navigate to the `webclient` directory:
    ```bash
    cd webclient
    ```

2.  **Install dependencies**:
    ```bash
    npm install
    ```

3.  **Configure Environment** (Optional):
    Create a `.env` file in `webclient/` to override the WebSocket URL if needed:
    ```
    VITE_WS_URL=ws://localhost:8000/ws/interview
    ```

## Usage

### Running the Server

Start the backend API and WebSocket server:

```bash
python start_server.py
```
*Alternatively:* `uvicorn server:app --reload --port 8000`

The server exposes:
- **REST API**: `http://127.0.0.1:8000/api/`
- **WebSocket**: `ws://127.0.0.1:8000/ws/interview`
- **Docs**: `http://127.0.0.1:8000/docs`

### Running the Frontend

Start the React development server:

```bash
cd webclient
npm run dev
```
Open your browser at `http://localhost:5173` to access the interview interface.

### Running the CLI Client (Legacy)

For testing without the frontend, you can use the command-line interface:

```bash
python app.py --mode camera
```
*Modes: `camera` (video), `screen` (screen share), `none` (audio only)*

## Database & Tools

- **Database Viewer**: Explore the database contents via CLI.
    ```bash
    python database_viewer.py
    ```
- **Test Scripts**:
    - `python test_database.py`: Run comprehensive database tests.
    - `python test_integration.py`: Verify API endpoint consistency.

## Project Structure

- `server.py`: Main FastAPI application and WebSocket handler.
- `app.py`: CLI client implementation.
- `database_operations.py`: Core logic for CRUD operations.
- `init_database.py`: Database schema setup and management.
- `live_config.py`: Configuration for Gemini Live API sessions.
- `score_candidate_with_db.py`: Utility to score interviews and save results.
- `webrtc_server.py`: WebRTC implementation for enhanced streaming.
- `webclient/`: React frontend application.
- `db/`: Directory containing the SQLite database.
- `recordings/`: Directory for storing interview audio and transcripts.

## Future Plans

See `FUTURE_PLAN.md` for the roadmap of upcoming features and enhancements.
