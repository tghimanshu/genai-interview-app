/**
 * React hook for WebRTC interview functionality
 * Provides easy integration with the interview application
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { WebRTCInterviewClient, WebRTCCallbacks } from "./webrtc-client";

export interface UseWebRTCOptions {
  websocketUrl?: string;
  autoConnect?: boolean;
  enableVideo?: boolean;
  enableAudio?: boolean;
}

export interface WebRTCState {
  isConnecting: boolean;
  isConnected: boolean;
  connectionState: RTCPeerConnectionState | null;
  error: Error | null;
  localStream: MediaStream | null;
  remoteAudioStream: MediaStream | null;
  remoteVideoStream: MediaStream | null;
}

export interface WebRTCControls {
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  toggleAudio: () => void;
  toggleVideo: () => void;
  getStats: () => Promise<RTCStatsReport | null>;
}

export function useWebRTC(
  sessionId: string,
  options: UseWebRTCOptions = {},
  onMessage?: (message: any) => void
): [WebRTCState, WebRTCControls] {
  const {
    websocketUrl = "ws://localhost:8000/ws/webrtc",
    autoConnect = false,
    enableVideo = true,
    enableAudio = true,
  } = options;

  // State
  const [state, setState] = useState<WebRTCState>({
    isConnecting: false,
    isConnected: false,
    connectionState: null,
    error: null,
    localStream: null,
    remoteAudioStream: null,
    remoteVideoStream: null,
  });

  // Refs
  const clientRef = useRef<WebRTCInterviewClient | null>(null);
  const audioEnabledRef = useRef(enableAudio);
  const videoEnabledRef = useRef(enableVideo);

  // WebRTC callbacks
  const callbacks: WebRTCCallbacks = {
    onConnectionStateChange: (connectionState) => {
      setState((prev) => ({
        ...prev,
        connectionState,
        isConnected: connectionState === "connected",
      }));
    },

    onDataReceived: (data) => {
      onMessage?.(data);
    },

    onError: (error) => {
      console.error("WebRTC Error:", error);
      setState((prev) => ({
        ...prev,
        error,
        isConnecting: false,
      }));
    },

    onRemoteAudio: (stream) => {
      setState((prev) => ({
        ...prev,
        remoteAudioStream: stream,
      }));
    },

    onRemoteVideo: (stream) => {
      setState((prev) => ({
        ...prev,
        remoteVideoStream: stream,
      }));
    },
  };

  // Connect function
  const connect = useCallback(async () => {
    if (clientRef.current?.getConnectionState()) {
      return; // Already connected
    }

    setState((prev) => ({
      ...prev,
      isConnecting: true,
      error: null,
    }));

    try {
      const client = new WebRTCInterviewClient(sessionId, callbacks, {
        audioConstraints: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
        videoConstraints: enableVideo
          ? {
              width: { ideal: 640 },
              height: { ideal: 480 },
              frameRate: { ideal: 30 },
            }
          : (false as any),
      });

      await client.connect(websocketUrl);
      clientRef.current = client;

      // Get local stream for display
      const localStream = client.getLocalVideoStream();
      setState((prev) => ({
        ...prev,
        localStream,
        isConnecting: false,
        isConnected: true,
      }));

      // Apply initial audio/video settings
      client.setAudioEnabled(audioEnabledRef.current);
      client.setVideoEnabled(videoEnabledRef.current && enableVideo);
    } catch (error) {
      setState((prev) => ({
        ...prev,
        error: error as Error,
        isConnecting: false,
      }));
      throw error;
    }
  }, [sessionId, websocketUrl, enableVideo, enableAudio]);

  // Disconnect function
  const disconnect = useCallback(async () => {
    if (clientRef.current) {
      await clientRef.current.disconnect();
      clientRef.current = null;
    }

    setState((prev) => ({
      ...prev,
      isConnected: false,
      isConnecting: false,
      connectionState: null,
      localStream: null,
      remoteAudioStream: null,
      remoteVideoStream: null,
    }));
  }, []);

  // Toggle audio
  const toggleAudio = useCallback(() => {
    audioEnabledRef.current = !audioEnabledRef.current;
    clientRef.current?.setAudioEnabled(audioEnabledRef.current);
  }, []);

  // Toggle video
  const toggleVideo = useCallback(() => {
    if (!enableVideo) return;

    videoEnabledRef.current = !videoEnabledRef.current;
    clientRef.current?.setVideoEnabled(videoEnabledRef.current);
  }, [enableVideo]);

  // Get stats
  const getStats = useCallback(async () => {
    return clientRef.current?.getStats() || null;
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
    };
  }, [autoConnect, connect]);

  // Controls object
  const controls: WebRTCControls = {
    connect,
    disconnect,
    toggleAudio,
    toggleVideo,
    getStats,
  };

  return [state, controls];
}

// Hook for playing remote audio streams
export function useRemoteAudio(stream: MediaStream | null) {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (stream && audioRef.current) {
      audioRef.current.srcObject = stream;
      audioRef.current.play().catch(console.error);
    }

    return () => {
      if (audioRef.current) {
        audioRef.current.srcObject = null;
      }
    };
  }, [stream]);

  // Create audio element if it doesn't exist
  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio();
      audioRef.current.autoplay = true;
    }

    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.srcObject = null;
      }
    };
  }, []);

  return audioRef.current;
}

// Hook for displaying video streams
export function useVideoDisplay(stream: MediaStream | null) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const setVideoElement = useCallback(
    (element: HTMLVideoElement | null) => {
      videoRef.current = element;

      if (element && stream) {
        element.srcObject = stream;
        element.play().catch(console.error);
      }
    },
    [stream]
  );

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
      videoRef.current.play().catch(console.error);
    }
  }, [stream]);

  return setVideoElement;
}
