"""
WebRTC Server Implementation for Live Interview System
Provides better real-time audio/video performance compared to WebSockets
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Optional, Set
from datetime import datetime
import cv2
import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaStreamTrack, MediaStreamError
from aiortc.mediastreams import MediaStreamTrack

from server import WebSocketInterviewSession
from live_config import MODEL, build_live_config
from enhanced_ai_config import get_enhanced_ai_config

logger = logging.getLogger(__name__)

# WebRTC Configuration
RTC_CONFIGURATION = RTCConfiguration([
    RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
    RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
])

class AudioTrack(MediaStreamTrack):
    """Custom audio track for processing interview audio"""
    
    kind = "audio"
    
    def __init__(self, interview_session: 'WebRTCInterviewSession'):
        super().__init__()
        self.interview_session = interview_session
        self._timestamp = 0
        
    async def recv(self):
        """Receive audio frames from the AI model"""
        try:
            # This would receive audio from the Gemini Live API
            # For now, return silence - will be implemented based on your existing audio logic
            pts, time_base = await self.next_timestamp()
            
            # Create silence frame (will be replaced with actual AI audio)
            frame = np.zeros((1024, 1), dtype=np.float32)
            
            from av import AudioFrame
            audio_frame = AudioFrame.from_ndarray(frame, format="flt", layout="mono")
            audio_frame.pts = pts
            audio_frame.time_base = time_base
            audio_frame.sample_rate = 24000
            
            return audio_frame
            
        except MediaStreamError:
            raise
        except Exception as e:
            logger.error(f"Error in AudioTrack.recv: {e}")
            raise MediaStreamError

class VideoTrack(MediaStreamTrack):
    """Custom video track for face detection and monitoring"""
    
    kind = "video"
    
    def __init__(self, interview_session: 'WebRTCInterviewSession'):
        super().__init__()
        self.interview_session = interview_session
        
    async def recv(self):
        """Process video frames for face detection"""
        try:
            # This will be used for face detection and look-away monitoring
            # For now, return a black frame
            pts, time_base = await self.next_timestamp()
            
            # Create black frame (placeholder)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            from av import VideoFrame
            video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
            video_frame.pts = pts
            video_frame.time_base = time_base
            
            return video_frame
            
        except MediaStreamError:
            raise
        except Exception as e:
            logger.error(f"Error in VideoTrack.recv: {e}")
            raise MediaStreamError

class WebRTCInterviewSession:
    """WebRTC-based interview session handler"""
    
    def __init__(self, websocket: WebSocket, resume_handle: Optional[str] = None):
        self.websocket = websocket
        self.session_id = str(uuid.uuid4())
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.resume_handle = resume_handle
        
        # Interview state
        self._looked_away = 0
        self._looked_away_warnings = 0
        self._session_terminated = False
        
        # Media tracks
        self.audio_track: Optional[AudioTrack] = None
        self.video_track: Optional[VideoTrack] = None
        
        # Face detection
        import pathlib
        BASE_DIR = pathlib.Path(__file__).resolve().parent
        haar_dir = BASE_DIR / "haarcascades"
        self._face_cascade = cv2.CascadeClassifier(
            str(haar_dir / "haarcascade_frontalface_default.xml")
        )
        
        logger.info(f"Created WebRTC session: {self.session_id}")
    
    async def handle_offer(self, peer_id: str, offer_data: dict):
        """Handle WebRTC offer from client"""
        try:
            pc = RTCPeerConnection(RTC_CONFIGURATION)
            self.peer_connections[peer_id] = pc
            
            # Set up audio and video tracks
            self.audio_track = AudioTrack(self)
            self.video_track = VideoTrack(self)
            
            pc.addTrack(self.audio_track)
            pc.addTrack(self.video_track)
            
            # Handle incoming tracks
            @pc.on("track")
            async def on_track(track):
                logger.info(f"Received {track.kind} track from peer {peer_id}")
                
                if track.kind == "audio":
                    asyncio.create_task(self.process_audio_track(track))
                elif track.kind == "video":
                    asyncio.create_task(self.process_video_track(track))
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state changed: {pc.connectionState}")
                if pc.connectionState == "failed":
                    await self.cleanup_peer(peer_id)
            
            # Set remote description
            offer = RTCSessionDescription(
                sdp=offer_data["sdp"],
                type=offer_data["type"]
            )
            await pc.setRemoteDescription(offer)
            
            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            # Send answer back to client
            await self.websocket.send_json({
                "type": "webrtc_answer",
                "peer_id": peer_id,
                "sdp": pc.localDescription.sdp,
                "sdp_type": pc.localDescription.type
            })
            
            logger.info(f"Sent WebRTC answer to peer {peer_id}")
            
        except Exception as e:
            logger.error(f"Error handling WebRTC offer: {e}")
            await self.websocket.send_json({
                "type": "webrtc_error",
                "error": f"Failed to handle offer: {str(e)}"
            })
    
    async def handle_ice_candidate(self, peer_id: str, candidate_data: dict):
        """Handle ICE candidate from client"""
        try:
            pc = self.peer_connections.get(peer_id)
            if not pc:
                logger.warning(f"No peer connection found for {peer_id}")
                return
            
            from aiortc import RTCIceCandidate
            candidate = RTCIceCandidate(
                candidate=candidate_data["candidate"],
                sdpMLineIndex=candidate_data["sdpMLineIndex"],
                sdpMid=candidate_data["sdpMid"]
            )
            
            await pc.addIceCandidate(candidate)
            logger.debug(f"Added ICE candidate for peer {peer_id}")
            
        except Exception as e:
            logger.error(f"Error handling ICE candidate: {e}")
    
    async def process_audio_track(self, track):
        """Process incoming audio from client"""
        try:
            while True:
                frame = await track.recv()
                
                # Convert audio frame to format expected by Gemini Live API
                # This replaces the WebSocket audio processing
                audio_data = frame.to_ndarray()
                
                # TODO: Send to Gemini Live API via existing session logic
                # This would replace the WebSocket audio sending mechanism
                
                await asyncio.sleep(0.02)  # 50fps audio processing
                
        except MediaStreamError:
            logger.info("Audio track ended")
        except Exception as e:
            logger.error(f"Error processing audio track: {e}")
    
    async def process_video_track(self, track):
        """Process incoming video for face detection"""
        try:
            while True:
                frame = await track.recv()
                
                # Convert to OpenCV format
                img = frame.to_ndarray(format="bgr24")
                
                # Face detection (existing logic from WebSocket implementation)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                )
                
                if len(faces) == 0:
                    self._looked_away += 1
                    
                    if self._looked_away >= 10:  # threshold
                        self._looked_away_warnings += 1
                        await self.websocket.send_json({
                            "type": "monitor",
                            "event": "look_away_warning",
                            "warnings": self._looked_away_warnings,
                            "remaining": max(0, 3 - self._looked_away_warnings)
                        })
                        self._looked_away = 0
                        
                        if self._looked_away_warnings >= 3:
                            await self.websocket.send_json({
                                "type": "monitor",
                                "event": "look_away_terminated"
                            })
                            self._session_terminated = True
                            break
                else:
                    self._looked_away = 0
                
                await asyncio.sleep(0.1)  # 10fps video processing
                
        except MediaStreamError:
            logger.info("Video track ended")
        except Exception as e:
            logger.error(f"Error processing video track: {e}")
    
    async def cleanup_peer(self, peer_id: str):
        """Clean up peer connection"""
        if peer_id in self.peer_connections:
            pc = self.peer_connections[peer_id]
            await pc.close()
            del self.peer_connections[peer_id]
            logger.info(f"Cleaned up peer connection: {peer_id}")
    
    async def cleanup(self):
        """Clean up all resources"""
        for peer_id in list(self.peer_connections.keys()):
            await self.cleanup_peer(peer_id)
        logger.info(f"Cleaned up WebRTC session: {self.session_id}")

# Store active sessions
active_sessions: Dict[str, WebRTCInterviewSession] = {}

async def handle_webrtc_message(websocket: WebSocket, message: dict):
    """Handle WebRTC signaling messages"""
    try:
        message_type = message.get("type")
        session_id = message.get("session_id")
        
        if not session_id:
            await websocket.send_json({
                "type": "error",
                "error": "Missing session_id"
            })
            return
        
        # Get or create session
        if session_id not in active_sessions:
            active_sessions[session_id] = WebRTCInterviewSession(websocket)
        
        session = active_sessions[session_id]
        
        if message_type == "webrtc_offer":
            peer_id = message.get("peer_id", "default")
            await session.handle_offer(peer_id, {
                "sdp": message["sdp"],
                "type": message["type_sdp"]
            })
            
        elif message_type == "webrtc_ice_candidate":
            peer_id = message.get("peer_id", "default")
            await session.handle_ice_candidate(peer_id, {
                "candidate": message["candidate"],
                "sdpMLineIndex": message["sdpMLineIndex"],
                "sdpMid": message["sdpMid"]
            })
            
        elif message_type == "webrtc_close":
            peer_id = message.get("peer_id", "default")
            await session.cleanup_peer(peer_id)
            
    except Exception as e:
        logger.error(f"Error handling WebRTC message: {e}")
        await websocket.send_json({
            "type": "webrtc_error",
            "error": str(e)
        })

async def cleanup_session(session_id: str):
    """Clean up session when WebSocket disconnects"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        await session.cleanup()
        del active_sessions[session_id]
        logger.info(f"Session cleaned up: {session_id}")