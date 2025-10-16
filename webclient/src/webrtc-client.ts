/**
 * WebRTC Client for Live Interview System
 * Provides better real-time audio/video performance compared to WebSockets
 */

export interface WebRTCConfig {
  iceServers: RTCIceServer[];
  audioConstraints: MediaTrackConstraints;
  videoConstraints: MediaTrackConstraints;
}

export interface WebRTCCallbacks {
  onConnectionStateChange?: (state: RTCPeerConnectionState) => void;
  onDataReceived?: (data: any) => void;
  onError?: (error: Error) => void;
  onRemoteAudio?: (stream: MediaStream) => void;
  onRemoteVideo?: (stream: MediaStream) => void;
}

export class WebRTCInterviewClient {
  private websocket: WebSocket | null = null;
  private peerConnection: RTCPeerConnection | null = null;
  private localStream: MediaStream | null = null;
  private sessionId: string;
  private callbacks: WebRTCCallbacks;
  private config: WebRTCConfig;
  private isConnected = false;

  constructor(
    sessionId: string,
    callbacks: WebRTCCallbacks,
    config?: Partial<WebRTCConfig>
  ) {
    this.sessionId = sessionId;
    this.callbacks = callbacks;
    this.config = {
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        { urls: "stun:stun1.l.google.com:19302" },
      ],
      audioConstraints: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 16000,
      },
      videoConstraints: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        frameRate: { ideal: 30 },
      },
      ...config,
    };
  }

  /**
   * Initialize WebRTC connection
   */
  async connect(websocketUrl: string): Promise<void> {
    try {
      // Setup WebSocket for signaling
      await this.setupWebSocket(websocketUrl);

      // Setup peer connection
      await this.setupPeerConnection();

      // Get user media
      await this.setupLocalMedia();

      // Create and send offer
      await this.createOffer();

      this.isConnected = true;
      console.log("WebRTC connection established");
    } catch (error) {
      console.error("Failed to establish WebRTC connection:", error);
      this.callbacks.onError?.(error as Error);
      throw error;
    }
  }

  /**
   * Setup WebSocket for signaling
   */
  private async setupWebSocket(url: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.websocket = new WebSocket(url);

      this.websocket.onopen = () => {
        console.log("WebRTC signaling WebSocket connected");
        resolve();
      };

      this.websocket.onmessage = (event) => {
        this.handleSignalingMessage(JSON.parse(event.data));
      };

      this.websocket.onerror = (error) => {
        console.error("WebSocket signaling error:", error);
        reject(error);
      };

      this.websocket.onclose = () => {
        console.log("WebRTC signaling WebSocket closed");
        this.isConnected = false;
      };
    });
  }

  /**
   * Setup RTCPeerConnection
   */
  private async setupPeerConnection(): Promise<void> {
    this.peerConnection = new RTCPeerConnection({
      iceServers: this.config.iceServers,
    });

    // Handle connection state changes
    this.peerConnection.onconnectionstatechange = () => {
      const state = this.peerConnection?.connectionState;
      console.log("WebRTC connection state:", state);
      this.callbacks.onConnectionStateChange?.(state!);
    };

    // Handle ICE candidates
    this.peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignalingMessage({
          type: "webrtc_ice_candidate",
          session_id: this.sessionId,
          peer_id: "default",
          candidate: event.candidate.candidate,
          sdpMLineIndex: event.candidate.sdpMLineIndex,
          sdpMid: event.candidate.sdpMid,
        });
      }
    };

    // Handle remote streams
    this.peerConnection.ontrack = (event) => {
      console.log("Received remote track:", event.track.kind);

      if (event.track.kind === "audio") {
        this.callbacks.onRemoteAudio?.(event.streams[0]);
      } else if (event.track.kind === "video") {
        this.callbacks.onRemoteVideo?.(event.streams[0]);
      }
    };
  }

  /**
   * Setup local media (audio/video)
   */
  private async setupLocalMedia(): Promise<void> {
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: this.config.audioConstraints,
        video: this.config.videoConstraints,
      });

      // Add tracks to peer connection
      this.localStream.getTracks().forEach((track) => {
        this.peerConnection?.addTrack(track, this.localStream!);
      });

      console.log("Local media setup complete");
    } catch (error) {
      console.error("Failed to get user media:", error);
      throw new Error("Failed to access camera/microphone");
    }
  }

  /**
   * Create and send offer
   */
  private async createOffer(): Promise<void> {
    if (!this.peerConnection) {
      throw new Error("Peer connection not initialized");
    }

    try {
      const offer = await this.peerConnection.createOffer();
      await this.peerConnection.setLocalDescription(offer);

      this.sendSignalingMessage({
        type: "webrtc_offer",
        session_id: this.sessionId,
        peer_id: "default",
        sdp: offer.sdp,
        type_sdp: offer.type,
      });

      console.log("WebRTC offer sent");
    } catch (error) {
      console.error("Failed to create offer:", error);
      throw error;
    }
  }

  /**
   * Handle signaling messages from server
   */
  private async handleSignalingMessage(message: any): Promise<void> {
    try {
      switch (message.type) {
        case "webrtc_answer":
          await this.handleAnswer(message);
          break;

        case "webrtc_ice_candidate":
          await this.handleIceCandidate(message);
          break;

        case "webrtc_error":
          console.error("WebRTC server error:", message.error);
          this.callbacks.onError?.(new Error(message.error));
          break;

        default:
          // Pass other messages to callback
          this.callbacks.onDataReceived?.(message);
      }
    } catch (error) {
      console.error("Error handling signaling message:", error);
      this.callbacks.onError?.(error as Error);
    }
  }

  /**
   * Handle answer from server
   */
  private async handleAnswer(message: any): Promise<void> {
    if (!this.peerConnection) {
      throw new Error("Peer connection not initialized");
    }

    const answer = new RTCSessionDescription({
      type: message.sdp_type as RTCSdpType,
      sdp: message.sdp,
    });

    await this.peerConnection.setRemoteDescription(answer);
    console.log("WebRTC answer received and processed");
  }

  /**
   * Handle ICE candidate from server
   */
  private async handleIceCandidate(message: any): Promise<void> {
    if (!this.peerConnection) {
      throw new Error("Peer connection not initialized");
    }

    const candidate = new RTCIceCandidate({
      candidate: message.candidate,
      sdpMLineIndex: message.sdpMLineIndex,
      sdpMid: message.sdpMid,
    });

    await this.peerConnection.addIceCandidate(candidate);
  }

  /**
   * Send signaling message to server
   */
  private sendSignalingMessage(message: any): void {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify(message));
    } else {
      console.error("WebSocket not connected, cannot send message");
    }
  }

  /**
   * Get local video stream for display
   */
  getLocalVideoStream(): MediaStream | null {
    return this.localStream;
  }

  /**
   * Mute/unmute local audio
   */
  setAudioEnabled(enabled: boolean): void {
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach((track) => {
        track.enabled = enabled;
      });
    }
  }

  /**
   * Enable/disable local video
   */
  setVideoEnabled(enabled: boolean): void {
    if (this.localStream) {
      this.localStream.getVideoTracks().forEach((track) => {
        track.enabled = enabled;
      });
    }
  }

  /**
   * Disconnect and cleanup
   */
  async disconnect(): Promise<void> {
    try {
      // Close peer connection
      if (this.peerConnection) {
        this.peerConnection.close();
        this.peerConnection = null;
      }

      // Stop local media
      if (this.localStream) {
        this.localStream.getTracks().forEach((track) => track.stop());
        this.localStream = null;
      }

      // Close WebSocket
      if (this.websocket) {
        this.sendSignalingMessage({
          type: "webrtc_close",
          session_id: this.sessionId,
          peer_id: "default",
        });

        this.websocket.close();
        this.websocket = null;
      }

      this.isConnected = false;
      console.log("WebRTC connection closed");
    } catch (error) {
      console.error("Error during WebRTC cleanup:", error);
    }
  }

  /**
   * Check if connected
   */
  getConnectionState(): boolean {
    return (
      this.isConnected && this.peerConnection?.connectionState === "connected"
    );
  }

  /**
   * Get connection statistics
   */
  async getStats(): Promise<RTCStatsReport | null> {
    if (this.peerConnection) {
      return await this.peerConnection.getStats();
    }
    return null;
  }
}
