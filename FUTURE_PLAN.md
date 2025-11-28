# Future Plan: Interview App Roadmap

This document outlines the current state of the Interview App (Phase 1) and details the roadmap for future enhancements (Phase 2 and beyond).

## Phase 1: Foundation (Current Status)

The current version of the application establishes the core infrastructure for AI-powered live interviews.

### Key Features Implemented
*   **Live Interview Engine**: Real-time audio/video interaction using Gemini Live API and WebSocket/WebRTC.
*   **Backend API**: Robust FastAPI server handling job descriptions, resumes, and interview management.
*   **Database Integration**: SQLite database with schema for:
    *   Job Descriptions & Resumes
    *   Interview Sessions & Metadata
    *   Match Ratings & Scoring Analysis
    *   System Events & Feedback
*   **Automated Scoring**: Post-interview analysis generating scores for technical skills, communication, and cultural fit.
*   **Resume Parsing**: Extraction of text and details from uploaded resumes.
*   **Proctoring Features**: Basic face tracking to detect if a candidate looks away frequently.
*   **Session Management**: Resume capability for interrupted sessions and audio recording/archiving.

### Completion Criteria for Phase 1
- [x] Stable WebSocket connection for live audio/video streaming.
- [x] Persistent storage of interview data and recordings.
- [x] reliable integration with GenAI models for conversation and scoring.
- [x] Basic frontend client for candidate interaction.
- [x] Comprehensive documentation of the codebase (This task).

---

## Phase 2: Enhanced Functionality & Scale

The next phase focuses on enterprise-readiness, user experience, and advanced analytics.

### 1. User Authentication & Role Management
*   **Objective**: Secure the application and support multiple user types (Recruiters, Admin, Candidates).
*   **Features**:
    *   JWT-based authentication.
    *   Role-based access control (RBAC).
    *   Secure candidate login via unique tokens/links.

### 2. Advanced Analytics & Dashboard
*   **Objective**: Provide actionable insights to hiring managers.
*   **Features**:
    *   Aggregate metrics (Time-to-hire, Average scores per job).
    *   Comparative analysis of candidates.
    *   Visual dashboard for interview performance trends.
    *   Exportable reports (PDF/CSV).

### 3. Enhanced WebRTC & Video Capabilities
*   **Objective**: Improve streaming quality and add video archiving.
*   **Features**:
    *   Full video recording (currently audio-focused).
    *   Adaptive bitrate streaming for poor connections.
    *   Screen sharing support for coding challenges.

### 4. Integrations & Workflow Automation
*   **Objective**: Fit seamlessly into existing HR workflows.
*   **Features**:
    *   **ATS Integration**: Connect with Greenhouse, Lever, etc.
    *   **Calendar Sync**: Auto-schedule interviews via Google Calendar/Outlook.
    *   **Email Notifications**: Customizable templates for invites, rejections, and offers.

### 5. Customizable Evaluation Frameworks
*   **Objective**: Allow tailoring the AI interviewer to specific needs.
*   **Features**:
    *   Custom rubric builder for different roles (e.g., System Design vs. Behavioral).
    *   Ability to upload specific coding questions or case studies.
    *   Fine-tuning prompts for different interviewer personas.

### 6. Security & Compliance
*   **Objective**: Ensure data privacy and legal compliance.
*   **Features**:
    *   GDPR/CCPA compliance tools (data anonymization, deletion requests).
    *   Data encryption at rest.
    *   Audit logs for all system actions.

## Phase 3: Long-term Vision

*   **Multi-modal AI Analysis**: Analyze facial expressions and tone of voice (sentiment analysis) alongside text.
*   **Collaborative Hiring**: Live observation mode for human recruiters to "sit in" and intervene.
*   **Mock Interview Platform**: A B2C version for candidates to practice and get feedback.
