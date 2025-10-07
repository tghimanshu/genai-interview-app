import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

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

type JobDescription = {
  id?: number;
  title: string;
  company: string;
  description_text: string;
  requirements?: string;
  skills_required?: string;
  experience_level?: string;
  location?: string;
  salary_range?: string;
  is_active?: boolean;
  created_at?: string;
};

type Resume = {
  id?: number;
  candidate_name: string;
  email?: string;
  phone?: string;
  resume_text: string;
  skills?: string;
  experience_years?: number;
  education?: string;
  is_active?: boolean;
  created_at?: string;
};

type Interview = {
  id?: number;
  session_id: string;
  job_description_id: number;
  resume_id: number;
  status: string;
  scheduled_at?: string;
  started_at?: string;
  ended_at?: string;
  duration_minutes?: number;
  created_at?: string;
};

type InterviewSummary = {
  interview_id: number;
  session_id: string;
  status: string;
  job_title: string;
  company: string;
  candidate_name: string;
  email: string;
  overall_match_score?: number;
  final_score?: number;
  final_decision?: string;
  started_at?: string;
  ended_at?: string;
  duration_minutes?: number;
};

type InterviewResults = {
  interview: Interview;
  job_description: JobDescription;
  resume: Resume;
  match_rating?: any;
  scoring_analysis?: any;
  final_score?: any;
  recordings?: any[];
  feedback?: any[];
};

type DatabaseStats = {
  totalJobs: number;
  totalCandidates: number;
  totalInterviews: number;
  averageScore: number;
};

type AISessionState = {
  sessionId: string;
  status: "connected" | "disconnected" | "connecting" | "error";
  lookAwayWarnings: number;
  sessionTerminated: boolean;
};

type AIMessage = {
  type: "audio" | "text" | "system" | "transcript";
  content: any;
  timestamp: number;
};

type InterviewSessionConfig = {
  resumeText?: string;
  jobDescriptionText?: string;
  sessionHandle?: string;
};

type AppView =
  | "interview"
  | "dashboard"
  | "jobs"
  | "candidates"
  | "results"
  | "analytics";

const DEFAULT_WS_URL =
  import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/interview";
const FALLBACK_SEND_SAMPLE_RATE = 16000;
const FRAME_INTERVAL_MS = 300;
const RESUME_STORAGE_KEY = "resumeText";
const JD_STORAGE_KEY = "jobDescriptionText";

const readStoredText = (key: string): string => {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch (error) {
    console.warn(`Unable to read ${key} from localStorage`, error);
    return "";
  }
};

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
  // Interview state
  const [status, setStatus] = useState<
    "disconnected" | "connecting" | "connected" | "error"
  >("disconnected");
  const [wsUrl, setWsUrl] = useState<string>(DEFAULT_WS_URL);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [transcriptsFormatted, setTranscriptsFormatted] = useState<Transcript[]>([]);

  const [inputText, setInputText] = useState<string>("");
  const [warningCount, setWarningCount] = useState<number>(0);
  const [remainingWarnings, setRemainingWarnings] = useState<number | null>(
    null
  );
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null);
  const [cameraEnabled, setCameraEnabled] = useState<boolean>(false);
  const [resumeText, setResumeText] = useState<string>(() =>
    readStoredText(RESUME_STORAGE_KEY)
  );
  const [jobDescriptionText, setJobDescriptionText] = useState<string>(() =>
    readStoredText(JD_STORAGE_KEY)
  );
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

  // AI Session state
  const [aiSessionState, setAiSessionState] = useState<AISessionState>({
    sessionId: "",
    status: "disconnected",
    lookAwayWarnings: 0,
    sessionTerminated: false,
  });
  const [currentInterviewData, setCurrentInterviewData] = useState<{
    interviewId?: string;
    jobTitle?: string;
    candidateName?: string;
  }>({});

  // Database state
  const [currentView, setCurrentView] = useState<AppView>("interview");
  const [jobDescriptions, setJobDescriptions] = useState<JobDescription[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [interviews, setInterviews] = useState<InterviewSummary[]>([]);
  const [selectedInterview, setSelectedInterview] =
    useState<InterviewResults | null>(null);
  const [databaseStats, setDatabaseStats] = useState<DatabaseStats | null>(
    null
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  // Form state
  const [editingJob, setEditingJob] = useState<JobDescription | null>(null);
  const [editingResume, setEditingResume] = useState<Resume | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);

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

  const appendTranscript = (role: "user" | "assistant", payload: unknown) => {
    const extractedText = extractTranscriptText(payload);
    if (!extractedText || extractedText.trim() === "") {
      return;
    }
    setTranscripts((prev) => {
      if (prev.length === 0) {
        return [
          {
            id: 1,
            role,
            text: extractedText,
            timestamp: Date.now(),
          },
        ];
      // } else if (prev[prev.length - 1].role === role) {
      //   const last = prev[prev.length - 1];
      //   last.text += extractedText;
      //   return [...prev.splice(0, -2), last];
      } else {
        return [
          ...prev,
          {
            id: prev[prev.length - 1].id + 1,
            role,
            text: extractedText,
            timestamp: Date.now(),
          },
        ];
      }
    });
  };
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
    setTranscriptsFormatted((_) => {
      if (transcripts.length === 0) {
        return [];
      } else {
        const formatted: Transcript[] = [];
        transcripts.map(item => {
          if (formatted.length === 0) {
            formatted.push({...item});
          } else {
            const last = formatted[formatted.length - 1];
            if (last.role === item.role) {
              last.text += item.text;
              formatted[formatted.length - 1] = last;
            } else {
              formatted.push({...item});
            }
          }
        })
        return formatted;
      }
    });
  }, [transcripts]);
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

  const sendContextUpdate = useCallback(() => {
    const trimmedResume = resumeText.trim();
    const trimmedJobDescription = jobDescriptionText.trim();
    if (!trimmedResume && !trimmedJobDescription) {
      appendMessage(
        "system",
        "Provide a resume and/or job description before sending context."
      );
      return;
    }
    baseSend({
      type: "context",
      resumeText: trimmedResume,
      jobDescriptionText: trimmedJobDescription,
    });
  }, [appendMessage, baseSend, jobDescriptionText, resumeText]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(RESUME_STORAGE_KEY, resumeText);
    } catch (error) {
      console.warn("Unable to persist resume text", error);
    }
  }, [resumeText]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(JD_STORAGE_KEY, jobDescriptionText);
    } catch (error) {
      console.warn("Unable to persist job description text", error);
    }
  }, [jobDescriptionText]);

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
            setAiSessionState((prev) => ({
              ...prev,
              sessionId: data.handle as string,
            }));
            appendMessage(
              "system",
              "Session resume handle updated. You can reconnect without losing context."
            );
          }
          break;
        }
        case "context_ack": {
          const updated = Array.isArray(data.updated) ? data.updated : [];
          if (updated.length > 0) {
            const labels = updated.map((field) =>
              field === "jobDescription" ? "job description" : field
            );
            appendMessage(
              "system",
              `Interview context updated (${labels.join(" & ")}).`
            );
          } else {
            appendMessage(
              "system",
              "Context update ignored. Provide a resume and/or job description to override the defaults."
            );
          }
          break;
        }
        case "error": {
          const message =
            typeof data.message === "string" ? data.message : "Server error";
          const details = typeof data.details === "string" ? data.details : "";
          appendMessage(
            "system",
            `Error: ${message}${details ? ` (${details})` : ""}`
          );
          setStatus("error");
          break;
        }
        case "session_expired": {
          const message =
            typeof data.message === "string"
              ? data.message
              : "Session expired. Please start a new interview.";
          appendMessage("system", message);

          // Clear the resume handle to force a fresh session
          setResumeHandle(null);
          resumeHandleRef.current = null;

          // Disconnect and set status
          manualDisconnectRef.current = true;
          reconnectAttemptsRef.current = 0;
          const ws = websocketRef.current;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.close(1000, "session expired");
          }
          setStatus("disconnected");
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
          const trimmedResume = resumeText.trim();
          const trimmedJobDescription = jobDescriptionText.trim();
          if (trimmedResume || trimmedJobDescription) {
            ws.send(
              JSON.stringify({
                type: "context",
                resumeText: trimmedResume,
                jobDescriptionText: trimmedJobDescription,
              })
            );
          }
        } catch (error) {
          console.error("Failed to send context payload", error);
        }

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
      jobDescriptionText,
      resumeText,
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

  // Database API functions
  const apiCall = async (endpoint: string, options?: RequestInit) => {
    const baseUrl = wsUrl
      .replace("ws://", "http://")
      .replace("wss://", "https://")
      .replace("/ws/interview", "");
    const response = await fetch(`${baseUrl}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(
        `API call failed: ${response.status} ${response.statusText}`
      );
    }

    return response.json();
  };

  const loadDashboardData = async () => {
    setLoading(true);
    setError("");
    try {
      const [statsData, interviewsData] = await Promise.all([
        apiCall("/api/analytics/stats"),
        apiCall("/api/interviews"),
      ]);
      setDatabaseStats(statsData);
      setInterviews(interviewsData.interviews || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load dashboard data"
      );
    } finally {
      setLoading(false);
    }
  };

  const loadJobDescriptions = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiCall("/api/jobs");
      setJobDescriptions(data.jobs || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load job descriptions"
      );
    } finally {
      setLoading(false);
    }
  };

  const loadResumes = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiCall("/api/resumes");
      setResumes(data.resumes || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load resumes");
    } finally {
      setLoading(false);
    }
  };

  const createJob = async (job: JobDescription) => {
    try {
      await apiCall("/api/jobs", {
        method: "POST",
        body: JSON.stringify(job),
      });
      await loadJobDescriptions();
      setEditingJob(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    }
  };

  const createResume = async (resume: Resume) => {
    try {
      await apiCall("/api/resumes", {
        method: "POST",
        body: JSON.stringify(resume),
      });
      await loadResumes();
      setEditingResume(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create resume");
    }
  };

  const createInterview = async () => {
    if (!selectedJobId || !selectedResumeId) {
      setError("Please select both a job and resume to create an interview");
      return;
    }

    try {
      setLoading(true);
      setError("");

      // Get job description and resume details
      const [jobData, resumeData] = await Promise.all([
        apiCall(`/api/jobs/${selectedJobId}`),
        apiCall(`/api/resumes/${selectedResumeId}`),
      ]);

      // Generate unique session ID
      const sessionId = `interview_${Date.now()}_${Math.random()
        .toString(36)
        .substr(2, 9)}`;

      // Create interview record
      const result = await apiCall("/api/interviews", {
        method: "POST",
        body: JSON.stringify({
          job_description_id: selectedJobId,
          resume_id: selectedResumeId,
          // session_id: sessionId,
          duration_minutes: null,
        }),
      });

      // Configure AI session with specific job and candidate context
      setJobDescriptionText(jobData.description_text || "");
      setResumeText(resumeData.resume_text || "");
      setResumeHandle(sessionId);

      // Update local storage with session info
      localStorage.setItem("currentInterviewId", result.id.toString());
      localStorage.setItem("currentJobTitle", jobData.title);
      localStorage.setItem("currentCandidateName", resumeData.candidate_name);

      // Switch to interview view
      setCurrentView("interview");

      // Show success message
      appendMessage(
        "system",
        `Interview session created for ${resumeData.candidate_name} - ${jobData.title} at ${jobData.company}`
      );

      // Clear selections
      setSelectedJobId(null);
      setSelectedResumeId(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create interview"
      );
    } finally {
      setLoading(false);
    }
  };

  const loadInterviewResults = async (interviewId: number) => {
    setLoading(true);
    setError("");
    try {
      const data = await apiCall(`/api/interviews/${interviewId}/results`);
      setSelectedInterview(data);
      setCurrentView("results");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load interview results"
      );
    } finally {
      setLoading(false);
    }
  };

  // Load data when view changes
  useEffect(() => {
    switch (currentView) {
      case "dashboard":
        loadDashboardData();
        break;
      case "jobs":
        loadJobDescriptions();
        break;
      case "candidates":
        loadResumes();
        break;
    }
  }, [currentView]);

  // Navigation component
  const Navigation = () => (
    <nav className="border-b border-slate-200/60 bg-white/60 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex space-x-1">
          <button
            className={`relative px-4 py-3 font-medium text-sm transition-all duration-200 rounded-t-lg ${
              currentView === "interview"
                ? "text-blue-600 bg-blue-50/80"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
            onClick={() => setCurrentView("interview")}
          >
            <span className="relative z-10">Live Interview</span>
            {currentView === "interview" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            )}
          </button>
          <button
            className={`relative px-4 py-3 font-medium text-sm transition-all duration-200 rounded-t-lg ${
              currentView === "dashboard"
                ? "text-blue-600 bg-blue-50/80"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
            onClick={() => setCurrentView("dashboard")}
          >
            <span className="relative z-10">Dashboard</span>
            {currentView === "dashboard" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            )}
          </button>
          <button
            className={`relative px-4 py-3 font-medium text-sm transition-all duration-200 rounded-t-lg ${
              currentView === "jobs"
                ? "text-blue-600 bg-blue-50/80"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
            onClick={() => setCurrentView("jobs")}
          >
            <span className="relative z-10">Job Descriptions</span>
            {currentView === "jobs" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            )}
          </button>
          <button
            className={`relative px-4 py-3 font-medium text-sm transition-all duration-200 rounded-t-lg ${
              currentView === "candidates"
                ? "text-blue-600 bg-blue-50/80"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
            onClick={() => setCurrentView("candidates")}
          >
            <span className="relative z-10">Candidates</span>
            {currentView === "candidates" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            )}
          </button>
          <button
            className={`relative px-4 py-3 font-medium text-sm transition-all duration-200 rounded-t-lg ${
              currentView === "results"
                ? "text-blue-600 bg-blue-50/80"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
            onClick={() =>
              loadDashboardData().then(() => setCurrentView("results"))
            }
          >
            <span className="relative z-10">Interview Results</span>
            {currentView === "results" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-indigo-600"></div>
            )}
          </button>
        </div>
      </div>
    </nav>
  );

  // Dashboard component
  const Dashboard = () => (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-slate-900 mb-2">
          Interview Dashboard
        </h2>
        <p className="text-slate-600">
          Monitor your interview process and candidate pipeline
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="relative">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200"></div>
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent absolute top-0 left-0"></div>
          </div>
          <span className="ml-4 text-slate-600 font-medium">
            Loading dashboard data...
          </span>
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-4 rounded-xl mb-8 flex items-start space-x-3">
          <svg
            className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <h4 className="font-medium">Error Loading Data</h4>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      )}

      {databaseStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          <div className="group bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-slate-200/60 p-6 hover:shadow-lg hover:shadow-blue-500/10 transition-all duration-300">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
            </div>
            <h3 className="text-sm font-medium text-slate-500 mb-2">
              Job Descriptions
            </h3>
            <div className="text-3xl font-bold text-slate-900 mb-1">
              {databaseStats.totalJobs}
            </div>
            <p className="text-xs text-slate-500">Active positions</p>
          </div>
          <div className="group bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-slate-200/60 p-6 hover:shadow-lg hover:shadow-emerald-500/10 transition-all duration-300">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                  />
                </svg>
              </div>
            </div>
            <h3 className="text-sm font-medium text-slate-500 mb-2">
              Candidates
            </h3>
            <div className="text-3xl font-bold text-slate-900 mb-1">
              {databaseStats.totalCandidates}
            </div>
            <p className="text-xs text-slate-500">In pipeline</p>
          </div>
          <div className="group bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-slate-200/60 p-6 hover:shadow-lg hover:shadow-purple-500/10 transition-all duration-300">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              </div>
            </div>
            <h3 className="text-sm font-medium text-slate-500 mb-2">
              Total Interviews
            </h3>
            <div className="text-3xl font-bold text-slate-900 mb-1">
              {databaseStats.totalInterviews}
            </div>
            <p className="text-xs text-slate-500">Completed sessions</p>
          </div>
          <div className="group bg-white/80 backdrop-blur-sm rounded-xl shadow-sm border border-slate-200/60 p-6 hover:shadow-lg hover:shadow-amber-500/10 transition-all duration-300">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-amber-500 to-orange-500 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                  />
                </svg>
              </div>
            </div>
            <h3 className="text-sm font-medium text-slate-500 mb-2">
              Average Score
            </h3>
            <div className="text-3xl font-bold text-slate-900 mb-1">
              {databaseStats.averageScore}
            </div>
            <p className="text-xs text-slate-500">Out of 10</p>
          </div>
        </div>
      )}

      {/* Recent Interviews Section */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden mb-8">
        <div className="bg-gradient-to-r from-slate-600 to-slate-700 px-8 py-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
              <svg
                className="w-6 h-6 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-white">Recent Interviews</h3>
          </div>
        </div>

        <div className="p-8">
          {interviews.length === 0 ? (
            <div className="text-center py-16">
              <svg
                className="w-20 h-20 text-slate-300 mx-auto mb-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
              <h4 className="text-2xl font-semibold text-slate-900 mb-3">
                No recent interviews found
              </h4>
              <p className="text-slate-600 mb-6 max-w-md mx-auto">
                Start conducting interviews to see them appear here with
                detailed analytics and results.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {(interviews || []).slice(0, 5).map((interview) => (
                <div
                  key={interview.interview_id}
                  className="group bg-slate-50/50 rounded-xl p-6 border border-slate-200 hover:shadow-lg hover:shadow-slate-500/10 transition-all duration-300"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-4 mb-3">
                        <div className="w-12 h-12 bg-gradient-to-br from-slate-600 to-slate-700 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                          <svg
                            className="w-6 h-6 text-white"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                            />
                          </svg>
                        </div>
                        <div className="flex-1">
                          <h4 className="text-lg font-bold text-slate-900 truncate">
                            {interview.candidate_name}
                          </h4>
                          <p className="text-sm text-slate-600">
                            {interview.job_title} • {interview.company}
                          </p>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                            Status
                          </p>
                          <span
                            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                              interview.status === "completed"
                                ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                : interview.status === "in_progress"
                                ? "bg-amber-100 text-amber-800 border border-amber-200"
                                : interview.status === "scheduled"
                                ? "bg-blue-100 text-blue-800 border border-blue-200"
                                : "bg-slate-100 text-slate-800 border border-slate-200"
                            }`}
                          >
                            {interview.status.replace("_", " ")}
                          </span>
                        </div>

                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                            Score
                          </p>
                          <div className="flex items-center space-x-2">
                            {interview.final_score ? (
                              <>
                                <span className="text-lg font-bold text-slate-900">
                                  {interview.final_score}
                                </span>
                                <span className="text-sm text-slate-500">
                                  /10
                                </span>
                              </>
                            ) : (
                              <span className="text-sm text-slate-500">
                                N/A
                              </span>
                            )}
                          </div>
                        </div>

                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                            Decision
                          </p>
                          {interview.final_decision ? (
                            <span
                              className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                                interview.final_decision === "hire"
                                  ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                  : interview.final_decision === "reject"
                                  ? "bg-red-100 text-red-800 border border-red-200"
                                  : "bg-amber-100 text-amber-800 border border-amber-200"
                              }`}
                            >
                              {interview.final_decision}
                            </span>
                          ) : (
                            <span className="text-sm text-slate-500">
                              Pending
                            </span>
                          )}
                        </div>

                        <div>
                          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                            Date
                          </p>
                          <p className="text-sm text-slate-900">
                            {interview.started_at
                              ? new Date(
                                  interview.started_at
                                ).toLocaleDateString("en-US", {
                                  month: "short",
                                  day: "numeric",
                                  year: "numeric",
                                })
                              : "Not started"}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="ml-4">
                      <button
                        onClick={() =>
                          loadInterviewResults(interview.interview_id)
                        }
                        className="inline-flex items-center px-4 py-2 bg-slate-600 text-white font-medium rounded-lg shadow-sm hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 transition-all duration-200"
                      >
                        <svg
                          className="w-4 h-4 mr-2"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
                        </svg>
                        View Results
                      </button>
                    </div>
                  </div>
                </div>
              ))}

              {interviews.length > 5 && (
                <div className="text-center pt-4">
                  <button
                    onClick={() => setCurrentView("results")}
                    className="inline-flex items-center px-6 py-3 text-slate-600 font-medium hover:text-slate-900 transition-colors duration-200"
                  >
                    View all {interviews.length} interviews
                    <svg
                      className="w-4 h-4 ml-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions Section */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden">
        <div className="bg-gradient-to-r from-indigo-600 to-purple-700 px-8 py-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
              <svg
                className="w-6 h-6 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-white">Quick Actions</h3>
          </div>
        </div>

        <div className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <button
              onClick={() => setCurrentView("jobs")}
              className="group relative p-6 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border-2 border-blue-200 hover:border-blue-300 hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-300 text-left"
            >
              <div className="flex items-center space-x-4 mb-4">
                <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2-2v2m8 0V6a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2V6z"
                    />
                  </svg>
                </div>
                <div>
                  <h4 className="text-lg font-bold text-slate-900 group-hover:text-blue-700 transition-colors duration-300">
                    Manage Jobs
                  </h4>
                  <p className="text-sm text-slate-600">
                    Create and edit job descriptions
                  </p>
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-b-xl transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300"></div>
            </button>

            <button
              onClick={() => setCurrentView("candidates")}
              className="group relative p-6 bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl border-2 border-emerald-200 hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-500/20 transition-all duration-300 text-left"
            >
              <div className="flex items-center space-x-4 mb-4">
                <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-green-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                    />
                  </svg>
                </div>
                <div>
                  <h4 className="text-lg font-bold text-slate-900 group-hover:text-emerald-700 transition-colors duration-300">
                    Manage Candidates
                  </h4>
                  <p className="text-sm text-slate-600">
                    Add and review candidate profiles
                  </p>
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-emerald-500 to-green-600 rounded-b-xl transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300"></div>
            </button>

            <button
              onClick={createInterview}
              disabled={loading || !selectedJobId || !selectedResumeId}
              className={`group relative p-6 rounded-xl border-2 transition-all duration-300 text-left ${
                loading || !selectedJobId || !selectedResumeId
                  ? "bg-slate-50 border-slate-200 cursor-not-allowed opacity-50"
                  : "bg-gradient-to-br from-purple-50 to-pink-50 border-purple-200 hover:border-purple-300 hover:shadow-lg hover:shadow-purple-500/20"
              }`}
            >
              <div className="flex items-center space-x-4 mb-4">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-300 ${
                    loading || !selectedJobId || !selectedResumeId
                      ? "bg-slate-300"
                      : "bg-gradient-to-br from-purple-500 to-pink-600 group-hover:scale-110"
                  }`}
                >
                  {loading ? (
                    <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                  ) : (
                    <svg
                      className="w-6 h-6 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                  )}
                </div>
                <div>
                  <h4
                    className={`text-lg font-bold transition-colors duration-300 ${
                      loading || !selectedJobId || !selectedResumeId
                        ? "text-slate-500"
                        : "text-slate-900 group-hover:text-purple-700"
                    }`}
                  >
                    {loading ? "Creating..." : "Start New Interview"}
                  </h4>
                  <p className="text-sm text-slate-600">
                    {!selectedJobId || !selectedResumeId
                      ? "Select job and candidate first"
                      : "Begin AI-powered interview session"}
                  </p>
                </div>
              </div>
              {!loading && !(!selectedJobId || !selectedResumeId) && (
                <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-purple-500 to-pink-600 rounded-b-xl transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300"></div>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  // console.log("Render MainApp");
  // console.log(transcripts);
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <header className="bg-white/80 backdrop-blur-sm shadow-sm border-b border-slate-200/60 px-6 py-5">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-lg flex items-center justify-center">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent">
              Interview Platform
            </h1>
          </div>
          <div className="flex items-center space-x-4">
            <div
              className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                status === "connected"
                  ? "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200"
                  : status === "connecting"
                  ? "bg-amber-100 text-amber-700 ring-1 ring-amber-200"
                  : "bg-red-100 text-red-700 ring-1 ring-red-200"
              }`}
            >
              <div
                className={`w-2 h-2 rounded-full mr-2 ${
                  status === "connected"
                    ? "bg-emerald-500"
                    : status === "connecting"
                    ? "bg-amber-500"
                    : "bg-red-500"
                }`}
              ></div>
              {status === "connected"
                ? "Live"
                : status === "connecting"
                ? "Connecting"
                : "Offline"}
            </div>
          </div>
        </div>
      </header>

      <Navigation />

      {/* Job Descriptions Management */}
      {currentView === "jobs" && (
        <div className="max-w-7xl mx-auto p-6">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-3xl font-bold text-slate-900 mb-2">
                Job Descriptions
              </h2>
              <p className="text-slate-600">
                Manage your open positions and requirements
              </p>
            </div>
            <button
              onClick={() =>
                setEditingJob({
                  title: "",
                  company: "",
                  description_text: "",
                  requirements: "",
                  skills_required: "",
                  experience_level: "",
                  location: "",
                  salary_range: "",
                })
              }
              className="inline-flex items-center px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium rounded-lg shadow-sm hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transform hover:scale-105 transition-all duration-200"
            >
              <svg
                className="w-5 h-5 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Add New Job
            </button>
          </div>

          {loading && <div className="loading">Loading...</div>}
          {error && <div className="error">{error}</div>}

          {editingJob && (
            <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-lg border border-slate-200/60 p-8 mb-8">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-slate-900">
                  {editingJob.id
                    ? "Edit Job Description"
                    : "Create New Job Description"}
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <input
                  placeholder="Job Title"
                  value={editingJob.title}
                  onChange={(e) =>
                    setEditingJob({ ...editingJob, title: e.target.value })
                  }
                  className="block w-full rounded-md border-gray-300 border px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <input
                  placeholder="Company Name"
                  value={editingJob.company}
                  onChange={(e) =>
                    setEditingJob({ ...editingJob, company: e.target.value })
                  }
                  className="block w-full rounded-md border-gray-300 border px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <input
                  placeholder="Location"
                  value={editingJob.location || ""}
                  onChange={(e) =>
                    setEditingJob({ ...editingJob, location: e.target.value })
                  }
                  className="block w-full rounded-md border-gray-300 border px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <input
                  placeholder="Salary Range"
                  value={editingJob.salary_range || ""}
                  onChange={(e) =>
                    setEditingJob({
                      ...editingJob,
                      salary_range: e.target.value,
                    })
                  }
                  className="block w-full rounded-md border-gray-300 border px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <textarea
                placeholder="Job Description"
                value={editingJob.description_text}
                onChange={(e) =>
                  setEditingJob({
                    ...editingJob,
                    description_text: e.target.value,
                  })
                }
                rows={6}
                className="block w-full rounded-md border-gray-300 border px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 mb-4"
              />
              <textarea
                placeholder="Requirements"
                value={editingJob.requirements || ""}
                onChange={(e) =>
                  setEditingJob({ ...editingJob, requirements: e.target.value })
                }
                rows={4}
                className="block w-full rounded-md border-gray-300 border px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 mb-4"
              />
              <div className="flex space-x-3">
                <button
                  onClick={() => createJob(editingJob)}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md font-medium transition-colors duration-200"
                >
                  {editingJob.id ? "Update" : "Create"} Job
                </button>
                <button
                  onClick={() => setEditingJob(null)}
                  className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-md font-medium transition-colors duration-200"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {(jobDescriptions || []).map((job) => (
              <div
                key={job.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
              >
                <div className="mb-4">
                  <h3 className="text-lg font-medium text-gray-900 mb-1">
                    {job.title}
                  </h3>
                  <span className="text-sm text-gray-500">{job.company}</span>
                </div>
                <p className="text-sm text-gray-600 mb-4 line-clamp-3">
                  {job.description_text.substring(0, 200)}...
                </p>
                <div className="space-y-1 mb-4 text-sm text-gray-500">
                  <div>Location: {job.location || "Not specified"}</div>
                  <div>Salary: {job.salary_range || "Not specified"}</div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => {
                      setSelectedJobId(job.id!);
                      setJobDescriptionText(job.description_text);
                    }}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200"
                  >
                    Select for Interview
                  </button>
                  <button
                    onClick={() => setEditingJob(job)}
                    className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200"
                  >
                    Edit
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Candidates Management */}
      {currentView === "candidates" && (
        <div className="max-w-7xl mx-auto p-6">
          {/* Page Header */}
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-slate-900 to-emerald-800 bg-clip-text text-transparent mb-2">
                  Candidate Management
                </h1>
                <p className="text-lg text-slate-600">
                  Manage your candidate pipeline and talent database
                </p>
              </div>
              <button
                onClick={() =>
                  setEditingResume({
                    candidate_name: "",
                    email: "",
                    phone: "",
                    resume_text: "",
                    skills: "",
                    education: "",
                    experience_years: 0,
                  })
                }
                className="inline-flex items-center px-6 py-3 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-medium rounded-xl shadow-lg hover:from-emerald-700 hover:to-green-700 focus:outline-none focus:ring-4 focus:ring-emerald-200 transform hover:scale-105 transition-all duration-200"
              >
                <svg
                  className="w-5 h-5 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Add New Candidate
              </button>
            </div>
          </div>

          {/* Loading State */}
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="relative">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-200"></div>
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-600 border-t-transparent absolute top-0 left-0"></div>
              </div>
              <span className="ml-4 text-slate-600 font-medium">
                Loading candidates...
              </span>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-4 rounded-xl mb-8 flex items-start space-x-3">
              <svg
                className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <div>
                <h4 className="font-medium">Error Loading Candidates</h4>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Candidate Form */}
          {editingResume && (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden mb-8">
              <div className="bg-gradient-to-r from-emerald-600 to-green-700 px-8 py-6">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-6 h-6 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      />
                    </svg>
                  </div>
                  <h3 className="text-2xl font-bold text-white">
                    {editingResume.id
                      ? "Edit Candidate Profile"
                      : "Create New Candidate"}
                  </h3>
                </div>
              </div>

              <div className="p-8">
                {/* Personal Information Section */}
                <div className="mb-8">
                  <h4 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
                    <svg
                      className="w-5 h-5 text-emerald-600 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      />
                    </svg>
                    Personal Information
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Full Name *
                      </label>
                      <input
                        type="text"
                        placeholder="Enter candidate's full name"
                        value={editingResume.candidate_name}
                        onChange={(e) =>
                          setEditingResume({
                            ...editingResume,
                            candidate_name: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-200"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Email Address
                      </label>
                      <input
                        type="email"
                        placeholder="candidate@example.com"
                        value={editingResume.email || ""}
                        onChange={(e) =>
                          setEditingResume({
                            ...editingResume,
                            email: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-200"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Phone Number
                      </label>
                      <input
                        type="tel"
                        placeholder="+1 (555) 123-4567"
                        value={editingResume.phone || ""}
                        onChange={(e) =>
                          setEditingResume({
                            ...editingResume,
                            phone: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-200"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Years of Experience
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="50"
                        placeholder="5"
                        value={editingResume.experience_years || ""}
                        onChange={(e) =>
                          setEditingResume({
                            ...editingResume,
                            experience_years: parseInt(e.target.value) || 0,
                          })
                        }
                        className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-200"
                      />
                    </div>
                  </div>
                </div>

                {/* Professional Information Section */}
                <div className="mb-8">
                  <h4 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
                    <svg
                      className="w-5 h-5 text-blue-600 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2-2v2m8 0V6a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2V6z"
                      />
                    </svg>
                    Professional Information
                  </h4>
                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Skills & Technologies
                      </label>
                      <input
                        type="text"
                        placeholder="React, TypeScript, Node.js, Python, AWS..."
                        value={editingResume.skills || ""}
                        onChange={(e) =>
                          setEditingResume({
                            ...editingResume,
                            skills: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 transition-all duration-200"
                      />
                      <p className="text-xs text-slate-500 mt-1">
                        Separate skills with commas
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Education
                      </label>
                      <input
                        type="text"
                        placeholder="Bachelor's in Computer Science, MIT"
                        value={editingResume.education || ""}
                        onChange={(e) =>
                          setEditingResume({
                            ...editingResume,
                            education: e.target.value,
                          })
                        }
                        className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 transition-all duration-200"
                      />
                    </div>
                  </div>
                </div>

                {/* Resume Content Section */}
                <div className="mb-8">
                  <h4 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
                    <svg
                      className="w-5 h-5 text-purple-600 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    Resume Content
                  </h4>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Full Resume Text *
                    </label>
                    <textarea
                      placeholder="Paste the complete resume content here...\n\nInclude work experience, achievements, projects, and any other relevant information."
                      value={editingResume.resume_text}
                      onChange={(e) =>
                        setEditingResume({
                          ...editingResume,
                          resume_text: e.target.value,
                        })
                      }
                      rows={10}
                      className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-200 transition-all duration-200 resize-y font-mono text-sm"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      This will be used by the AI interviewer to assess the
                      candidate
                    </p>
                  </div>
                </div>

                {/* Form Actions */}
                <div className="flex flex-col sm:flex-row gap-4 pt-6 border-t border-slate-200">
                  <button
                    onClick={() => createResume(editingResume)}
                    disabled={
                      !editingResume.candidate_name ||
                      !editingResume.resume_text
                    }
                    className="flex-1 inline-flex items-center justify-center px-6 py-3 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-medium rounded-lg shadow-lg hover:from-emerald-700 hover:to-green-700 focus:outline-none focus:ring-4 focus:ring-emerald-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                  >
                    <svg
                      className="w-5 h-5 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    {editingResume.id ? "Update Candidate" : "Create Candidate"}
                  </button>
                  <button
                    onClick={() => setEditingResume(null)}
                    className="px-6 py-3 bg-slate-600 text-white font-medium rounded-lg shadow-sm hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 transition-all duration-200"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Candidates Grid */}
          {(resumes || []).length === 0 && !loading ? (
            <div className="text-center py-16">
              <svg
                className="w-20 h-20 text-slate-300 mx-auto mb-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
              <h3 className="text-2xl font-semibold text-slate-900 mb-3">
                No candidates yet
              </h3>
              <p className="text-slate-600 mb-6 max-w-md mx-auto">
                Start building your talent pipeline by adding your first
                candidate profile.
              </p>
              <button
                onClick={() =>
                  setEditingResume({
                    candidate_name: "",
                    email: "",
                    phone: "",
                    resume_text: "",
                    skills: "",
                    education: "",
                    experience_years: 0,
                  })
                }
                className="inline-flex items-center px-6 py-3 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-medium rounded-lg shadow-lg hover:from-emerald-700 hover:to-green-700 focus:outline-none focus:ring-4 focus:ring-emerald-200 transform hover:scale-105 transition-all duration-200"
              >
                <svg
                  className="w-5 h-5 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Add First Candidate
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
              {(resumes || []).map((resume) => {
                const skillsArray = resume.skills
                  ? resume.skills
                      .split(",")
                      .map((s) => s.trim())
                      .filter((s) => s)
                  : [];
                const isSelected = selectedResumeId === resume.id;

                return (
                  <div
                    key={resume.id}
                    className={`group bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border transition-all duration-300 hover:shadow-xl hover:shadow-emerald-500/10 ${
                      isSelected
                        ? "border-emerald-400 ring-2 ring-emerald-200 shadow-emerald-500/20"
                        : "border-slate-200/60 hover:border-emerald-300"
                    }`}
                  >
                    {/* Card Header */}
                    <div className="p-6 border-b border-slate-100">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center space-x-3">
                          <div
                            className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                              isSelected
                                ? "bg-gradient-to-br from-emerald-500 to-green-600"
                                : "bg-gradient-to-br from-slate-600 to-slate-700 group-hover:from-emerald-500 group-hover:to-green-600"
                            } transition-all duration-300`}
                          >
                            <svg
                              className="w-6 h-6 text-white"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                              />
                            </svg>
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className="text-xl font-bold text-slate-900 truncate">
                              {resume.candidate_name}
                            </h3>
                            {isSelected && (
                              <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-emerald-100 text-emerald-700 mt-1">
                                <svg
                                  className="w-3 h-3 mr-1"
                                  fill="currentColor"
                                  viewBox="0 0 20 20"
                                >
                                  <path
                                    fillRule="evenodd"
                                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                    clipRule="evenodd"
                                  />
                                </svg>
                                Selected
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col items-end space-y-2">
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                            {resume.experience_years}{" "}
                            {resume.experience_years === 1 ? "year" : "years"}
                          </span>
                        </div>
                      </div>

                      {/* Contact Information */}
                      <div className="space-y-2 text-sm">
                        {resume.email && (
                          <div className="flex items-center text-slate-600">
                            <svg
                              className="w-4 h-4 mr-2 text-slate-400"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207"
                              />
                            </svg>
                            <span className="truncate">{resume.email}</span>
                          </div>
                        )}
                        {resume.phone && (
                          <div className="flex items-center text-slate-600">
                            <svg
                              className="w-4 h-4 mr-2 text-slate-400"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                              />
                            </svg>
                            <span>{resume.phone}</span>
                          </div>
                        )}
                        {resume.education && (
                          <div className="flex items-center text-slate-600">
                            <svg
                              className="w-4 h-4 mr-2 text-slate-400"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 14l9-5-9-5-9 5 9 5z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z"
                              />
                            </svg>
                            <span className="truncate">{resume.education}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Card Content */}
                    <div className="p-6">
                      {/* Skills */}
                      {skillsArray.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-slate-700 mb-2">
                            Skills & Technologies
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {skillsArray.slice(0, 6).map((skill, index) => (
                              <span
                                key={index}
                                className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200"
                              >
                                {skill}
                              </span>
                            ))}
                            {skillsArray.length > 6 && (
                              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
                                +{skillsArray.length - 6} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Resume Preview */}
                      <div className="mb-6">
                        <h4 className="text-sm font-medium text-slate-700 mb-2">
                          Resume Summary
                        </h4>
                        <p className="text-sm text-slate-600 leading-relaxed line-clamp-4">
                          {resume.resume_text.length > 300
                            ? resume.resume_text.substring(0, 300) + "..."
                            : resume.resume_text ||
                              "No resume content available"}
                        </p>
                      </div>
                    </div>

                    {/* Card Actions */}
                    <div className="p-6 pt-0">
                      <div className="flex flex-col sm:flex-row gap-3">
                        <button
                          onClick={() => {
                            setSelectedResumeId(resume.id!);
                            setResumeText(resume.resume_text);
                          }}
                          className={`flex-1 inline-flex items-center justify-center px-4 py-2.5 font-medium rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 transition-all duration-200 ${
                            isSelected
                              ? "bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-emerald-500"
                              : "bg-gradient-to-r from-emerald-600 to-green-600 text-white hover:from-emerald-700 hover:to-green-700 focus:ring-emerald-500"
                          }`}
                        >
                          <svg
                            className="w-4 h-4 mr-2"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                            />
                          </svg>
                          {isSelected ? "Selected" : "Select for Interview"}
                        </button>
                        <button
                          onClick={() => setEditingResume(resume)}
                          className="px-4 py-2.5 bg-slate-600 text-white font-medium rounded-lg shadow-sm hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 transition-all duration-200 flex items-center justify-center"
                        >
                          <svg
                            className="w-4 h-4 mr-2"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                            />
                          </svg>
                          Edit
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Interview Results */}
      {currentView === "results" && (
        <div className="results-container">
          {loading && (
            <div className="loading">Loading interview results...</div>
          )}
          {error && <div className="error">{error}</div>}
          {selectedInterview && (
            <div className="interview-results">
              <div className="section-header">
                <h2>Interview Results</h2>
                <button
                  onClick={() => setCurrentView("dashboard")}
                  className="secondary-btn"
                >
                  Back to Dashboard
                </button>
              </div>

              <div className="results-overview">
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <h3 className="text-sm font-medium text-gray-500 mb-2">
                    Final Score
                  </h3>
                  <div className="text-3xl font-bold text-gray-900">
                    {selectedInterview.final_score?.final_score || "N/A"}/10
                  </div>
                </div>
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <h3 className="text-sm font-medium text-gray-500 mb-2">
                    Decision
                  </h3>
                  <div
                    className={`px-3 py-2 rounded-lg text-sm font-medium ${
                      selectedInterview.final_score?.final_decision === "hired"
                        ? "bg-green-100 text-green-800"
                        : selectedInterview.final_score?.final_decision ===
                          "rejected"
                        ? "bg-red-100 text-red-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {selectedInterview.final_score?.final_decision || "Pending"}
                  </div>
                </div>
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                  <h3 className="text-sm font-medium text-gray-500 mb-2">
                    Match Score
                  </h3>
                  <div className="text-3xl font-bold text-gray-900">
                    {selectedInterview.match_rating?.overall_match_score ||
                      "N/A"}
                    %
                  </div>
                </div>
              </div>

              {selectedInterview.scoring_analysis && (
                <div className="detailed-scores">
                  <h3>Detailed Analysis</h3>
                  <div className="score-breakdown">
                    <div className="score-item">
                      <span>Technical Skills:</span>
                      <span>
                        {selectedInterview.scoring_analysis
                          .technical_skills_score || "N/A"}
                        /10
                      </span>
                    </div>
                    <div className="score-item">
                      <span>Problem Solving:</span>
                      <span>
                        {selectedInterview.scoring_analysis
                          .problem_solving_score || "N/A"}
                        /10
                      </span>
                    </div>
                    <div className="score-item">
                      <span>Communication:</span>
                      <span>
                        {selectedInterview.scoring_analysis
                          .communication_score || "N/A"}
                        /10
                      </span>
                    </div>
                    <div className="score-item">
                      <span>Cultural Fit:</span>
                      <span>
                        {selectedInterview.scoring_analysis
                          .cultural_fit_score || "N/A"}
                        /10
                      </span>
                    </div>
                  </div>

                  {selectedInterview.scoring_analysis.detailed_feedback && (
                    <div className="feedback-section">
                      <h4>Detailed Feedback</h4>
                      <div className="feedback-content">
                        {selectedInterview.scoring_analysis.detailed_feedback}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="interview-info">
                <h3>Interview Details</h3>
                <div className="info-grid">
                  <div>
                    <strong>Candidate:</strong>{" "}
                    {selectedInterview.resume.candidate_name}
                  </div>
                  <div>
                    <strong>Position:</strong>{" "}
                    {selectedInterview.job_description.title}
                  </div>
                  <div>
                    <strong>Company:</strong>{" "}
                    {selectedInterview.job_description.company}
                  </div>
                  <div>
                    <strong>Duration:</strong>{" "}
                    {selectedInterview.interview.duration_minutes || "N/A"}{" "}
                    minutes
                  </div>
                  <div>
                    <strong>Status:</strong>{" "}
                    {selectedInterview.interview.status}
                  </div>
                  <div>
                    <strong>Session ID:</strong>{" "}
                    {selectedInterview.interview.session_id}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Live Interview Section */}
      {currentView === "interview" && (
        <div className="max-w-7xl mx-auto p-6 space-y-8">
          {/* Page Header */}
          <div className="text-center">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-900 to-blue-800 bg-clip-text text-transparent mb-4">
              Live Interview Platform
            </h1>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Conduct AI-powered interviews with real-time feedback and
              comprehensive analysis
            </p>
          </div>

          {/* Interview Setup Card */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden">
            <div className="bg-gradient-to-r from-blue-600 to-indigo-700 px-8 py-6">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
                    />
                  </svg>
                </div>
                <h2 className="text-2xl font-bold text-white">
                  Interview Setup
                </h2>
              </div>
            </div>

            <div className="p-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                {/* Selected Job Card */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2-2v2m8 0V6a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2V6z"
                        />
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900">
                      Selected Job Position
                    </h3>
                  </div>
                  <div className="text-2xl font-bold text-blue-700 mb-2">
                    {selectedJobId
                      ? jobDescriptions.find((j) => j.id === selectedJobId)
                          ?.title || "Unknown Position"
                      : "No Job Selected"}
                  </div>
                  <p className="text-sm text-slate-600">
                    {selectedJobId
                      ? jobDescriptions.find((j) => j.id === selectedJobId)
                          ?.company || "Company not specified"
                      : "Please select a job position from the Job Descriptions section"}
                  </p>
                </div>

                {/* Selected Candidate Card */}
                <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl p-6 border border-emerald-200">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                        />
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900">
                      Selected Candidate
                    </h3>
                  </div>
                  <div className="text-2xl font-bold text-emerald-700 mb-2">
                    {selectedResumeId
                      ? resumes.find((r) => r.id === selectedResumeId)
                          ?.candidate_name || "Unknown Candidate"
                      : "No Candidate Selected"}
                  </div>
                  <p className="text-sm text-slate-600">
                    {selectedResumeId
                      ? `${
                          resumes.find((r) => r.id === selectedResumeId)
                            ?.experience_years || 0
                        } years of experience`
                      : "Please select a candidate from the Candidates section"}
                  </p>
                </div>
              </div>

              {/* Create Interview Button */}
              <div className="text-center">
                <button
                  onClick={createInterview}
                  disabled={!selectedJobId || !selectedResumeId}
                  className="inline-flex items-center px-8 py-4 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-bold text-lg rounded-xl shadow-lg hover:from-emerald-700 hover:to-green-700 focus:outline-none focus:ring-4 focus:ring-emerald-200 disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
                >
                  <svg
                    className="w-6 h-6 mr-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>
                  Create Interview Session
                </button>
                {(!selectedJobId || !selectedResumeId) && (
                  <p className="mt-3 text-sm text-amber-600 bg-amber-50 px-4 py-2 rounded-lg inline-block">
                    ⚠️ Please select both a job position and a candidate to
                    start the interview
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Connection Controls */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden">
            <div className="bg-gradient-to-r from-purple-600 to-pink-600 px-8 py-6">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"
                    />
                  </svg>
                </div>
                <h2 className="text-2xl font-bold text-white">
                  Connection Settings
                </h2>
              </div>
            </div>

            <div className="p-8">
              {/* WebSocket URL Input */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-slate-700 mb-3">
                  WebSocket Server URL
                </label>
                <input
                  type="text"
                  value={wsUrl}
                  onChange={(event) => setWsUrl(event.target.value)}
                  placeholder="ws://localhost:8000/ws/interview"
                  className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-200 transition-all duration-200 font-mono text-sm"
                />
              </div>

              {/* Connection Buttons */}
              <div className="flex flex-wrap gap-4 mb-8">
                <button
                  type="button"
                  onClick={() => void connect()}
                  disabled={status === "connected" || status === "connecting"}
                  className="inline-flex items-center px-6 py-3 bg-gradient-to-r from-emerald-600 to-green-600 text-white font-medium rounded-lg shadow-sm hover:from-emerald-700 hover:to-green-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  <svg
                    className="w-5 h-5 mr-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                  Connect
                </button>
                <button
                  type="button"
                  onClick={() => void disconnect()}
                  disabled={status === "disconnected"}
                  className="inline-flex items-center px-6 py-3 bg-gradient-to-r from-red-600 to-pink-600 text-white font-medium rounded-lg shadow-sm hover:from-red-700 hover:to-pink-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  <svg
                    className="w-5 h-5 mr-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                  Disconnect
                </button>
              </div>

              {/* Status Information Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Look-away Warnings */}
                <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-6 border border-amber-200">
                  <div className="flex items-center space-x-3 mb-3">
                    <div className="w-8 h-8 bg-amber-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                    </div>
                    <h3 className="font-semibold text-slate-900">
                      Look-away Warnings
                    </h3>
                  </div>
                  <div className="text-3xl font-bold text-amber-700">
                    {warningCount}
                  </div>
                  <p className="text-sm text-slate-600 mt-1">
                    {remainingWarnings !== null && remainingWarnings >= 0
                      ? `${remainingWarnings} warnings remaining`
                      : "Monitor engagement"}
                  </p>
                </div>

                {/* Send Rate */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                  <div className="flex items-center space-x-3 mb-3">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
                        />
                      </svg>
                    </div>
                    <h3 className="font-semibold text-slate-900">Send Rate</h3>
                  </div>
                  <div className="text-3xl font-bold text-blue-700">
                    {serverInfo?.sendSampleRate ?? FALLBACK_SEND_SAMPLE_RATE}
                  </div>
                  <p className="text-sm text-slate-600 mt-1">Hz</p>
                </div>

                {/* Receive Rate */}
                <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl p-6 border border-emerald-200">
                  <div className="flex items-center space-x-3 mb-3">
                    <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                        />
                      </svg>
                    </div>
                    <h3 className="font-semibold text-slate-900">
                      Receive Rate
                    </h3>
                  </div>
                  <div className="text-3xl font-bold text-emerald-700">
                    {serverInfo?.receiveSampleRate ?? "auto"}
                  </div>
                  <p className="text-sm text-slate-600 mt-1">Hz</p>
                </div>
              </div>
            </div>
          </div>
          {/* Interview Context */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden">
            <div className="bg-gradient-to-r from-indigo-600 to-blue-700 px-8 py-6">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                </div>
                <h2 className="text-2xl font-bold text-white">
                  Interview Context
                </h2>
              </div>
            </div>

            <div className="p-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                {/* Resume Section */}
                <div className="space-y-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                        />
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900">
                      Candidate Resume
                    </h3>
                  </div>
                  <textarea
                    value={resumeText}
                    onChange={(event) => setResumeText(event.target.value)}
                    rows={8}
                    placeholder="Paste or type the candidate's resume here..."
                    className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-200 resize-y font-mono text-sm"
                  />
                </div>

                {/* Job Description Section */}
                <div className="space-y-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                      <svg
                        className="w-5 h-5 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2-2v2m8 0V6a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2V6z"
                        />
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900">
                      Job Description
                    </h3>
                  </div>
                  <textarea
                    value={jobDescriptionText}
                    onChange={(event) =>
                      setJobDescriptionText(event.target.value)
                    }
                    rows={8}
                    placeholder="Paste or type the job description here..."
                    className="w-full px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 transition-all duration-200 resize-y font-mono text-sm"
                  />
                </div>
              </div>

              {/* Context Actions */}
              <div className="flex flex-col items-center space-y-4">
                <button
                  type="button"
                  onClick={sendContextUpdate}
                  disabled={status !== "connected"}
                  className="inline-flex items-center px-8 py-4 bg-gradient-to-r from-indigo-600 to-blue-600 text-white font-medium text-lg rounded-xl shadow-lg hover:from-indigo-700 hover:to-blue-700 focus:outline-none focus:ring-4 focus:ring-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  <svg
                    className="w-6 h-6 mr-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                    />
                  </svg>
                  Send Context to Interviewer
                </button>

                <div
                  className={`px-6 py-3 rounded-lg text-sm font-medium ${
                    status === "connected"
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-amber-50 text-amber-700 border border-amber-200"
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <span>
                      {status === "connected"
                        ? "Use this button to refresh the interviewer's context mid-session"
                        : "Your text is saved locally and will be sent automatically on the next connection"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Session Handle */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 p-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 bg-gradient-to-br from-slate-600 to-slate-700 rounded-lg flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">
                    Session Handle
                  </h3>
                  <p className="text-sm text-slate-600">
                    Unique identifier for this interview session
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <div className="text-right">
                  <div className="text-sm text-slate-600">Current Handle:</div>
                  <code className="text-lg font-mono bg-slate-100 px-3 py-1 rounded-lg">
                    {resumeHandle || "Not yet issued"}
                  </code>
                </div>
                <button
                  type="button"
                  onClick={() => clearResumeHandle()}
                  disabled={
                    !resumeHandle ||
                    status === "connected" ||
                    status === "connecting"
                  }
                  className="px-4 py-2 bg-gradient-to-r from-red-600 to-pink-600 text-white font-medium rounded-lg shadow-sm hover:from-red-700 hover:to-pink-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  Clear Handle
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Dashboard View */}
      {currentView === "dashboard" && <Dashboard />}

      {/* Live Chat Section - Only show when connected and interview view is active */}
      {currentView === "interview" && status === "connected" && (
        <div className="max-w-7xl mx-auto px-6 pb-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Live Conversation */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden">
              <div className="bg-gradient-to-r from-emerald-600 to-teal-700 px-6 py-4">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                      />
                    </svg>
                  </div>
                  <h3 className="text-xl font-bold text-white">
                    Live Conversation
                  </h3>
                </div>
              </div>

              <div className="p-6">
                <div className="space-y-4 max-h-96 overflow-y-auto custom-scrollbar mb-6">
                  {(messages || []).length === 0 ? (
                    <div className="text-center py-12">
                      <svg
                        className="w-16 h-16 text-slate-300 mx-auto mb-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                        />
                      </svg>
                      <p className="text-slate-500 font-medium">
                        No conversation yet
                      </p>
                      <p className="text-sm text-slate-400">
                        Start chatting with the AI interviewer
                      </p>
                    </div>
                  ) : (
                    (messages || []).map((message) => (
                      <div
                        key={message.id}
                        className={`p-4 rounded-xl shadow-sm border transition-all duration-200 hover:shadow-md ${
                          message.role === "user"
                            ? "bg-blue-50/80 border-blue-200 ml-8"
                            : message.role === "assistant"
                            ? "bg-emerald-50/80 border-emerald-200 mr-8"
                            : "bg-slate-50/80 border-slate-200"
                        }`}
                      >
                        <span className="text-xs font-medium text-slate-600 uppercase tracking-wide">
                          {message.role}
                        </span>
                        <p className="mt-1 text-slate-900">{message.text}</p>
                      </div>
                    ))
                  )}
                </div>

                <form
                  onSubmit={handleSubmit}
                  className="flex gap-3 p-4 bg-slate-50/80 rounded-xl border border-slate-200"
                >
                  <input
                    type="text"
                    value={inputText}
                    onChange={(event) => setInputText(event.target.value)}
                    placeholder="Send a message to the interviewer..."
                    disabled={status !== "connected"}
                    className="flex-1 px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 transition-all duration-200 disabled:bg-slate-100 disabled:text-slate-400"
                  />
                  <button
                    type="submit"
                    disabled={status !== "connected" || !inputText.trim()}
                    className="px-6 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-medium rounded-lg shadow-sm hover:from-emerald-700 hover:to-teal-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center space-x-2"
                  >
                    <span>Send</span>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                      />
                    </svg>
                  </button>
                </form>
              </div>
            </div>

            {/* Live Transcripts */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-lg border border-slate-200/60 overflow-hidden">
              <div className="bg-gradient-to-r from-purple-600 to-pink-600 px-6 py-4">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-white"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                      />
                    </svg>
                  </div>
                  <h3 className="text-xl font-bold text-white">
                    Live Transcripts
                  </h3>
                </div>
              </div>

              <div className="p-6">
                <div className="space-y-3 max-h-96 overflow-y-auto custom-scrollbar">
                  {(transcriptsFormatted || []).length === 0 ? (
                    <div className="text-center py-12">
                      <svg
                        className="w-16 h-16 text-slate-300 mx-auto mb-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                        />
                      </svg>
                      <p className="text-slate-500 font-medium">
                        No transcripts yet
                      </p>
                      <p className="text-sm text-slate-400">
                        Audio transcripts will appear here
                      </p>
                    </div>
                  ) : (
                    (transcriptsFormatted || []).map((item) => (
                      <div
                        key={item.id}
                        className={`p-4 rounded-xl border-l-4 shadow-sm transition-all duration-200 hover:shadow-md ${
                          item.role === "user"
                            ? "bg-blue-50/80 border-l-blue-400"
                            : "bg-emerald-50/80 border-l-emerald-400"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-slate-600 uppercase tracking-wide">
                            {item.role}
                          </span>
                          <span className="text-xs text-slate-500">
                            {new Date(item.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-sm text-slate-900">{item.text}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Legacy Content Section for Non-Interview Views */}
      {currentView !== "interview" && (
        <section className="content">
          <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-lg border border-slate-200/60 p-6">
            <div className="flex items-center space-x-3 mb-6">
              <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-slate-900">
                Live Conversation
              </h2>
            </div>
            <div className="space-y-4 max-h-96 overflow-y-auto custom-scrollbar">
              {(messages || []).map((message) => (
                <div
                  key={message.id}
                  className={`p-4 rounded-xl shadow-sm border transition-all duration-200 hover:shadow-md ${
                    message.role === "user"
                      ? "bg-blue-50/80 border-blue-200 ml-8"
                      : message.role === "assistant"
                      ? "bg-emerald-50/80 border-emerald-200 mr-8"
                      : "bg-slate-50/80 border-slate-200"
                  }`}
                >
                  <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
                    {message.role}
                  </span>
                  <p className="mt-1 text-gray-900">{message.text}</p>
                </div>
              ))}
            </div>
            <form
              onSubmit={handleSubmit}
              className="flex gap-3 mt-6 p-4 bg-slate-50/80 rounded-xl border border-slate-200"
            >
              <input
                type="text"
                value={inputText}
                onChange={(event) => setInputText(event.target.value)}
                placeholder="Send a text prompt to the interviewer..."
                disabled={status !== "connected"}
                className="flex-1 px-4 py-3 rounded-lg border-2 border-slate-300 bg-white/70 backdrop-blur-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 transition-all duration-200 disabled:bg-slate-100 disabled:text-slate-400"
              />
              <button
                type="submit"
                disabled={status !== "connected" || !inputText.trim()}
                className="px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium rounded-lg shadow-sm hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center space-x-2"
              >
                <span>Send</span>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              </button>
            </form>
          </div>

          <div className="bg-white/80 backdrop-blur-sm rounded-xl shadow-lg border border-slate-200/60 p-6">
            <div className="flex items-center space-x-3 mb-6">
              <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-slate-900">
                Live Transcripts
              </h2>
            </div>
            <div className="space-y-3 max-h-96 overflow-y-auto custom-scrollbar">
              {(transcripts || []).map((item) => (
                <div
                  key={item.id}
                  className={`p-4 rounded-xl border-l-4 shadow-sm transition-all duration-200 hover:shadow-md ${
                    item.role === "user"
                      ? "bg-blue-50/80 border-l-blue-400"
                      : "bg-emerald-50/80 border-l-emerald-400"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
                      {item.role}
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-900">{item.text}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Camera Preview - Hidden for now */}
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
        </div> 
        */}
        </section>
      )}
    </div>
  );
};

export default App;
