import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import "./App.css";

type Role = "system" | "user" | "assistant";

type ChatMessage = {
  id: number;
  role: Role;
  text: string;
};

type Transcript = {
  id: number;
  role: "user" | "assistant";
  text: string;
  timestamp: number;
};

type ServerInfo = {
  sendSampleRate?: number;
  receiveSampleRate?: number;
};

const DEFAULT_WS_URL =
  import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/interview";
const FALLBACK_SEND_SAMPLE_RATE = 16000;
const FRAME_INTERVAL_MS = 300;

function arrayBufferToBase64(
  buffer: ArrayBufferLike,
  offset = 0,
  length?: number
): string {
  const bytes = new Uint8Array(
    buffer,
    offset,
    length ?? buffer.byteLength - offset
  );
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const slice = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...slice);
  }
  return btoa(binary);
}

function base64ToUint8Array(base64: string): Uint8Array {
  const binary = atob(base64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function downsampleBuffer(
  buffer: Float32Array,
  inputRate: number,
  targetRate: number
): Float32Array {
  if (targetRate === inputRate) {
    return buffer;
  }
  const ratio = inputRate / targetRate;
  const newLength = Math.round(buffer.length / ratio);
  if (!Number.isFinite(newLength) || newLength <= 0) {
    return new Float32Array(0);
  }
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (
      let i = offsetBuffer;
      i < nextOffsetBuffer && i < buffer.length;
      i += 1
    ) {
      accum += buffer[i];
      count += 1;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function floatTo16BitPCM(float32: Float32Array): Int16Array {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i += 1) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16;
}

function int16ToFloat32(int16: Int16Array): Float32Array {
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i += 1) {
    float32[i] = int16[i] / 0x8000;
  }
  return float32;
}

function extractTranscriptText(payload: unknown): string {
  if (!payload) {
    return "";
  }
  if (typeof payload === "string") {
    return payload;
  }
  if (typeof payload === "object") {
    const obj = payload as Record<string, unknown>;
    if (typeof obj.text === "string") {
      return obj.text;
    }
    if (typeof obj.transcript === "string") {
      return obj.transcript;
    }
    if (Array.isArray(obj.segments)) {
      return obj.segments
        .map((segment: unknown) => {
          if (segment && typeof segment === "object" && "text" in segment) {
            return String((segment as Record<string, unknown>).text ?? "");
          }
          return "";
        })
        .join(" ")
        .trim();
    }
    if (Array.isArray(obj.transcripts)) {
      return obj.transcripts
        .map((entry: unknown) => {
          if (entry && typeof entry === "object" && "text" in entry) {
            return String((entry as Record<string, unknown>).text ?? "");
          }
          return "";
        })
        .join(" ")
        .trim();
    }
  }
  try {
    return JSON.stringify(payload);
  } catch (error) {
    return "";
  }
}

function buildConnectionUrl(
  baseUrl: string,
  resumeHandle?: string | null
): string {
  if (!resumeHandle) {
    return baseUrl;
  }

  try {
    const url = new URL(baseUrl);
    url.searchParams.set("resume", resumeHandle);
    return url.toString();
  } catch (error) {
    const separator = baseUrl.includes("?") ? "&" : "?";
    return `${baseUrl}${separator}resume=${encodeURIComponent(resumeHandle)}`;
  }
}

const App = () => {
  const [status, setStatus] = useState<
    "disconnected" | "connecting" | "connected" | "error"
  >("disconnected");
  const [wsUrl, setWsUrl] = useState<string>(DEFAULT_WS_URL);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [transcriptsRole, setTranscriptsRole] = useState<string>("");
  const [inputText, setInputText] = useState<string>("");
  const [warningCount, setWarningCount] = useState<number>(0);
  const [remainingWarnings, setRemainingWarnings] = useState<number | null>(
    null
  );
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null);
  const [cameraEnabled, setCameraEnabled] = useState<boolean>(false);
  const [resumeHandle, setResumeHandle] = useState<string | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    try {
      return window.localStorage.getItem("resumeHandle");
    } catch (error) {
      console.warn("Unable to access localStorage", error);
      return null;
    }
  });

  const websocketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const playbackTimeRef = useRef<number>(0);
  const videoStreamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameIntervalRef = useRef<number | null>(null);
  const messageIdRef = useRef<number>(0);
  const transcriptIdRef = useRef<number>(0);
  const resumeHandleRef = useRef<string | null>(resumeHandle);
  const manualDisconnectRef = useRef<boolean>(false);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const connectionAttemptRef = useRef<boolean>(false);

  const appendMessage = useCallback((role: Role, text: string) => {
    if (!text) {
      return;
    }
    messageIdRef.current += 1;
    setMessages((prev) => [
      ...prev,
      {
        id: messageIdRef.current,
        role,
        text,
      },
    ]);
  }, []);

  const appendTranscript = useCallback(
    (role: "user" | "assistant", payload: unknown) => {
      const text = extractTranscriptText(payload);
      if (!text) {
        return;
      }
      if (transcriptsRole !== role) {
        setTranscriptsRole(role);
        transcriptIdRef.current += 1;
        setTranscripts((prev) => [
            ...prev,
            {
            id: transcriptIdRef.current,
            role,
            text,
            timestamp: Date.now(),
            },
        ]);
      } else {
        setTranscripts((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === role) {
            last.text += `${text}`;
            return [...prev.slice(0, -1), last];
          }
        });
      }

      //   const text = extractTranscriptText(payload);
      //   if (!text) {
      //     return;
      //   }
      //   transcriptIdRef.current += 1;
      //   setTranscripts((prev) => [
      //     ...prev.slice(-99),
      //     {
      //       id: transcriptIdRef.current,
      //       role,
      //       text,
      //       timestamp: Date.now(),
      //     },
      //   ]);
    },
    []
  );

  const ensureAudioContext = useCallback(async (): Promise<AudioContext> => {
    let ctx = audioContextRef.current;
    if (!ctx) {
      ctx = new AudioContext();
      audioContextRef.current = ctx;
    }
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    return ctx;
  }, []);

  useEffect(() => {
    resumeHandleRef.current = resumeHandle;
    try {
      if (resumeHandle) {
        window.localStorage.setItem("resumeHandle", resumeHandle);
      } else {
        window.localStorage.removeItem("resumeHandle");
      }
    } catch (error) {
      console.warn("Unable to persist resume handle", error);
    }
  }, [resumeHandle]);

  const baseSend = useCallback((payload: Record<string, unknown>) => {
    const ws = websocketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  }, []);

  const clearResumeHandle = useCallback(() => {
    setResumeHandle(null);
    appendMessage(
      "system",
      "Stored session handle cleared. Next connection will start a fresh interview."
    );
  }, [appendMessage]);

  const sendAudio = useCallback(
    (pcm: Int16Array) => {
      baseSend({
        type: "audio",
        data: arrayBufferToBase64(pcm.buffer, pcm.byteOffset, pcm.byteLength),
      });
    },
    [baseSend]
  );

  const sendFrame = useCallback(
    (base64Frame: string) => {
      baseSend({ type: "image", mime_type: "image/jpeg", data: base64Frame });
    },
    [baseSend]
  );

  const stopVideoCapture = useCallback(async () => {
    if (frameIntervalRef.current !== null) {
      window.clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
    if (videoStreamRef.current) {
      videoStreamRef.current.getTracks().forEach((track) => track.stop());
      videoStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }
  }, []);

  const startVideoCapture = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 },
      audio: false,
    });
    videoStreamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
    }
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    canvas.width = 320;
    canvas.height = 240;
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    frameIntervalRef.current = window.setInterval(() => {
      const videoEl = videoRef.current;
      if (!videoEl || videoEl.readyState < 2) {
        return;
      }
      context.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.6);
      const base64 = dataUrl.split(",")[1];
      if (base64) {
        sendFrame(base64);
      }
    }, FRAME_INTERVAL_MS);
  }, [sendFrame]);

  const stopAudioCapture = useCallback(async () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }
    if (gainRef.current) {
      gainRef.current.disconnect();
      gainRef.current = null;
    }
    if (micSourceRef.current) {
      micSourceRef.current.disconnect();
      micSourceRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    if (audioContextRef.current) {
      await audioContextRef.current.close();
      audioContextRef.current = null;
    }
    playbackTimeRef.current = 0;
  }, []);

  const cleanupMedia = useCallback(async () => {
    await stopAudioCapture();
    await stopVideoCapture();
  }, [stopAudioCapture, stopVideoCapture]);

  const startAudioCapture = useCallback(async () => {
    const ctx = await ensureAudioContext();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: ctx.sampleRate,
      },
      video: false,
    });
    micStreamRef.current = stream;
    const source = ctx.createMediaStreamSource(stream);
    micSourceRef.current = source;
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;
    const gain = ctx.createGain();
    gain.gain.value = 0;
    gainRef.current = gain;

    source.connect(processor);
    processor.connect(gain);
    gain.connect(ctx.destination);

    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      const desiredRate =
        serverInfo?.sendSampleRate ?? FALLBACK_SEND_SAMPLE_RATE;
      const downsampled = downsampleBuffer(input, ctx.sampleRate, desiredRate);
      if (!downsampled.length) {
        return;
      }
      const pcm = floatTo16BitPCM(downsampled);
      sendAudio(pcm);
    };
  }, [ensureAudioContext, sendAudio, serverInfo?.sendSampleRate]);

  const playAssistantAudio = useCallback(
    async (base64: string, sampleRate?: number) => {
      const ctx = await ensureAudioContext();
      const bytes = base64ToUint8Array(base64);
      if (bytes.byteLength % 2 !== 0) {
        return;
      }
      const buffer = new ArrayBuffer(bytes.byteLength);
      new Uint8Array(buffer).set(bytes);
      const pcm = new Int16Array(buffer);
      if (pcm.length === 0) {
        return;
      }
      const floats = int16ToFloat32(pcm);
      const targetSampleRate =
        sampleRate ?? serverInfo?.receiveSampleRate ?? ctx.sampleRate;
      const audioBuffer = ctx.createBuffer(1, floats.length, targetSampleRate);
      audioBuffer.copyToChannel(Float32Array.from(floats), 0);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);

      const now = ctx.currentTime;
      const startAt = Math.max(
        now + 0.05,
        playbackTimeRef.current || now + 0.05
      );
      source.start(startAt);
      playbackTimeRef.current = startAt + audioBuffer.duration;
    },
    [ensureAudioContext, serverInfo?.receiveSampleRate]
  );

  const handleServerMessage = useCallback(
    async (event: MessageEvent<string>) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error("Failed to parse message", error);
        return;
      }
      const type = data.type;
      switch (type) {
        case "status": {
          const info: ServerInfo = {
            sendSampleRate:
              typeof data.sendSampleRate === "number"
                ? data.sendSampleRate
                : undefined,
            receiveSampleRate:
              typeof data.receiveSampleRate === "number"
                ? data.receiveSampleRate
                : undefined,
          };
          setServerInfo(info);
          if (typeof data.resumeHandle === "string" && data.resumeHandle) {
            setResumeHandle(data.resumeHandle);
          }
          setStatus((prev) => (prev === "connecting" ? "connected" : prev));
          appendMessage("system", "Connected to interview server.");
          break;
        }
        case "audio": {
          if (typeof data.data === "string") {
            const sampleRate =
              typeof data.sampleRate === "number" ? data.sampleRate : undefined;
            await playAssistantAudio(data.data, sampleRate);
          }
          break;
        }
        case "text": {
          if (typeof data.text === "string") {
            appendMessage("assistant", data.text);
          }
          break;
        }
        case "transcript": {
          if (typeof data.role === "string") {
            const role = data.role === "user" ? "user" : "assistant";
            appendTranscript(role, data.payload);
          }
          break;
        }
        case "monitor": {
          if (data.event === "look_away_warning") {
            const warnings =
              typeof data.warnings === "number"
                ? data.warnings
                : warningCount + 1;
            const remaining =
              typeof data.remaining === "number" ? data.remaining : null;
            setWarningCount(warnings);
            setRemainingWarnings(remaining);
            appendMessage("system", `Eye-contact warning ${warnings}.`);
          } else if (data.event === "look_away_terminated") {
            setWarningCount(
              typeof data.warnings === "number" ? data.warnings : warningCount
            );
            setRemainingWarnings(0);
            appendMessage(
              "system",
              "Session will conclude due to repeated look-aways."
            );
          }
          break;
        }
        case "recordings": {
          const sessionId =
            typeof data.sessionId === "string" ? data.sessionId : "unknown";
          const parts: string[] = [];
          if (typeof data.assistantPath === "string") {
            parts.push(`assistant: ${data.assistantPath}`);
          }
          if (typeof data.candidatePath === "string") {
            parts.push(`candidate: ${data.candidatePath}`);
          }
          if (typeof data.mixPath === "string") {
            parts.push(`mix: ${data.mixPath}`);
          }
          if (typeof data.transcriptsPath === "string") {
            parts.push(`transcripts: ${data.transcriptsPath}`);
          }
          if (parts.length > 0) {
            appendMessage(
              "system",
              `Artifacts for session ${sessionId} saved -> ${parts.join(", ")}`
            );
          }
          break;
        }
        case "session_complete": {
          const reason =
            typeof data.reason === "string" ? data.reason : "completed";
          const detail =
            typeof data.detail === "string" && data.detail ? data.detail : null;
          const detailSuffix = detail ? `: ${detail}` : "";
          appendMessage(
            "system",
            `Session complete (${reason})${detailSuffix}`
          );
          manualDisconnectRef.current = true;
          reconnectAttemptsRef.current = 0;
          resumeHandleRef.current = null;
          setResumeHandle(null);
          const ws = websocketRef.current;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.close(1000, "session complete");
          }
          setStatus("disconnected");
          break;
        }
        case "session_resumption": {
          if (typeof data.handle === "string" && data.handle) {
            setResumeHandle(data.handle);
            appendMessage(
              "system",
              "Session resume handle updated. You can reconnect without losing context."
            );
          }
          break;
        }
        case "error": {
          const message =
            typeof data.message === "string" ? data.message : "Server error";
          appendMessage("system", message);
          setStatus("error");
          break;
        }
        default:
          console.debug("Unhandled message", data);
      }
    },
    [
      appendMessage,
      appendTranscript,
      playAssistantAudio,
      warningCount,
      setResumeHandle,
      setStatus,
    ]
  );

  const connect = useCallback(
    async (isReconnect = false) => {
      if (websocketRef.current || connectionAttemptRef.current) {
        return;
      }

      if (!isReconnect && reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      connectionAttemptRef.current = true;
      manualDisconnectRef.current = false;
      if (!isReconnect) {
        reconnectAttemptsRef.current = 0;
      }

      const connectionUrl = buildConnectionUrl(wsUrl, resumeHandleRef.current);
      setStatus("connecting");
      const ws = new WebSocket(connectionUrl);
      websocketRef.current = ws;

      ws.onopen = async () => {
        try {
          await startAudioCapture();
          if (cameraEnabled && !videoStreamRef.current) {
            await startVideoCapture();
          }
          reconnectAttemptsRef.current = 0;
          connectionAttemptRef.current = false;
          setStatus("connected");
          if (isReconnect) {
            appendMessage(
              "system",
              "Reconnected to interview session using stored handle."
            );
          }
        } catch (error) {
          console.error("Failed to initialise media", error);
          connectionAttemptRef.current = false;
          setStatus("error");
          ws.close();
        }
      };

      ws.onmessage = (event) => {
        void handleServerMessage(event);
      };

      ws.onerror = (event) => {
        console.error("WebSocket error", event);
        connectionAttemptRef.current = false;
        setStatus("error");
      };

      ws.onclose = async () => {
        connectionAttemptRef.current = false;
        websocketRef.current = null;
        await cleanupMedia();

        if (reconnectTimeoutRef.current !== null) {
          window.clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }

        if (!manualDisconnectRef.current && resumeHandleRef.current) {
          reconnectAttemptsRef.current += 1;
          if (reconnectAttemptsRef.current > 5) {
            setStatus("error");
            appendMessage(
              "system",
              "Reached maximum reconnection attempts. Please reconnect manually."
            );
            return;
          }

          const delay = Math.min(
            10000,
            1000 * 2 ** Math.max(0, reconnectAttemptsRef.current - 1)
          );
          setStatus("connecting");
          appendMessage(
            "system",
            `Connection lost. Attempting to resume in ${Math.round(
              delay / 1000
            )}s (try ${reconnectAttemptsRef.current}/5).`
          );
          reconnectTimeoutRef.current = window.setTimeout(() => {
            void connect(true);
          }, delay);
        } else {
          setStatus("disconnected");
        }
      };
    },
    [
      appendMessage,
      cameraEnabled,
      cleanupMedia,
      handleServerMessage,
      startAudioCapture,
      startVideoCapture,
      wsUrl,
    ]
  );

  const disconnect = useCallback(async () => {
    manualDisconnectRef.current = true;
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttemptsRef.current = 0;

    const ws = websocketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "control", action: "stop" }));
      ws.close();
    } else if (ws) {
      ws.close();
    } else {
      await cleanupMedia();
      connectionAttemptRef.current = false;
      setStatus("disconnected");
    }
  }, [cleanupMedia]);

  useEffect(() => {
    return () => {
      manualDisconnectRef.current = true;
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      void disconnect();
    };
  }, [disconnect]);

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!inputText.trim()) {
        return;
      }
      appendMessage("user", inputText.trim());
      baseSend({ type: "text", text: inputText.trim(), turn_complete: true });
      setInputText("");
    },
    [appendMessage, baseSend, inputText]
  );

  const handleToggleCamera = useCallback(async () => {
    if (cameraEnabled) {
      setCameraEnabled(false);
      await stopVideoCapture();
    } else {
      try {
        await startVideoCapture();
        setCameraEnabled(true);
      } catch (error) {
        console.error("Unable to start camera", error);
        setCameraEnabled(false);
      }
    }
  }, [cameraEnabled, startVideoCapture, stopVideoCapture]);

  return (
    <div className="app">
      <header>
        <h1>Live Interview Client</h1>
        <div className={`status ${status}`}>
          Status: <span>{status}</span>
        </div>
      </header>

      <section className="controls">
        <div className="connection-controls">
          <input
            type="text"
            value={wsUrl}
            onChange={(event) => setWsUrl(event.target.value)}
            placeholder="WebSocket URL"
          />
          <button
            type="button"
            onClick={() => void connect()}
            disabled={status === "connected" || status === "connecting"}
          >
            Connect
          </button>
          <button
            type="button"
            onClick={() => void disconnect()}
            disabled={status === "disconnected"}
          >
            Disconnect
          </button>
          {/* <button type="button" onClick={() => void handleToggleCamera()}>
            {cameraEnabled ? "Stop Camera" : "Start Camera"}
          </button> */}
        </div>
        <div className="warning-indicator">
          <strong>Look-away warnings:</strong> {warningCount}
          {remainingWarnings !== null && remainingWarnings >= 0
            ? ` (remaining: ${remainingWarnings})`
            : null}
        </div>
        <div className="server-info">
          <span>
            Send rate: {serverInfo?.sendSampleRate ?? FALLBACK_SEND_SAMPLE_RATE}{" "}
            Hz
          </span>
          <span>Receive rate: {serverInfo?.receiveSampleRate ?? "auto"}</span>
        </div>
        <div className="session-handle">
          <span>
            Session handle:{" "}
            {resumeHandle ? <code>{resumeHandle}</code> : "Not yet issued"}
          </span>
          <button
            type="button"
            onClick={() => clearResumeHandle()}
            disabled={
              !resumeHandle || status === "connected" || status === "connecting"
            }
          >
            Clear stored handle
          </button>
        </div>
      </section>

      <section className="content">
        <div className="conversation">
          <h2>Conversation</h2>
          <div className="messages">
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.role}`}>
                <span className="role">{message.role}</span>
                <p>{message.text}</p>
              </div>
            ))}
          </div>
          <form onSubmit={handleSubmit} className="message-form">
            <input
              type="text"
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              placeholder="Send a text prompt to the interviewer"
              disabled={status !== "connected"}
            />
            <button
              type="submit"
              disabled={status !== "connected" || !inputText.trim()}
            >
              Send
            </button>
          </form>
        </div>

        <div className="transcripts">
          <h2>Live Transcripts</h2>
          <div className="transcript-list">
            {transcripts.map((item) => (
              <div key={item.id} className={`transcript ${item.role}`}>
                <span className="role">{item.role}</span>
                <span className="time">
                  {new Date(item.timestamp).toLocaleTimeString()}
                </span>
                <p>{item.text}</p>
              </div>
            ))}
          </div>
        </div>
{/* 
        <div className="preview">
          <h2>Camera Preview</h2>
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className={cameraEnabled ? "visible" : "hidden"}
          />
          <canvas ref={canvasRef} className="hidden" />
          <p>
            {cameraEnabled
              ? "Streaming camera frames to server."
              : "Camera is currently off."}
          </p>
        </div> */}
      </section>
    </div>
  );
};

export default App;
