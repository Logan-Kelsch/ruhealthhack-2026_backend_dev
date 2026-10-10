// Opens ElevenLabs Scribe v2 Realtime from the browser. The token is single-use.
// The long-lived key never reaches this file.

import type { ScribeConnectOptions, ScribeEvent, ScribeSession, ScribeWord } from "./scribe";

const SCRIBE_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime";
const SAMPLE_RATE = 16000;

// Turns a socket message into one encounter event. Plain commits wait briefly so a
// timestamp message for the same words can replace them.
export function connectElevenLabsScribe(options: ScribeConnectOptions): Promise<ScribeSession> {
  return openScribe(options);
}

// Asks for the microphone, then the socket. A failure releases whichever one already opened.
async function openScribe(options: ScribeConnectOptions): Promise<ScribeSession> {
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: options.echoCancellation,
        noiseSuppression: options.noiseSuppression,
        autoGainControl: true,
      },
    });
  } catch (error) {
    // The browser names a denied prompt NotAllowedError. The encounter shows that case itself.
    throw error;
  }

  const socket = new WebSocket(scribeUrl(options));
  try {
    await waitUntilOpen(socket);
  } catch (error) {
    stopTracks(stream);
    throw error;
  }

  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  // ScriptProcessor still runs in current browsers and lets us mute without a worklet file.
  const processor = context.createScriptProcessor(4096, 1, 1);
  let muted = false;
  let stopped = false;
  let skipPlain = "";
  let plainTimer: number | null = null;

  processor.onaudioprocess = (event) => {
    if (muted || stopped || socket.readyState !== WebSocket.OPEN) return;
    const samples = event.inputBuffer.getChannelData(0);
    const pcm = downsampleToPcm16(samples, context.sampleRate, SAMPLE_RATE);
    socket.send(
      JSON.stringify({
        message_type: "input_audio_chunk",
        audio_base_64: pcm16ToBase64(pcm),
        commit: false,
        sample_rate: SAMPLE_RATE,
      }),
    );
    // The processor must stay connected. Silence on the output keeps the mic out of the speakers.
    event.outputBuffer.getChannelData(0).fill(0);
  };
  source.connect(processor);
  processor.connect(context.destination);

  socket.addEventListener("message", (message) => {
    if (stopped || typeof message.data !== "string") return;
    let payload: unknown;
    try {
      payload = JSON.parse(message.data);
    } catch {
      return;
    }
    const event = readServerEvent(payload, () => skipPlain, (text) => {
      skipPlain = text;
    });
    if (event === "hold-plain") {
      const text = textOf(payload);
      if (plainTimer !== null) window.clearTimeout(plainTimer);
      // A timestamp message usually follows at once. Waiting avoids submitting the same turn twice.
      plainTimer = window.setTimeout(() => {
        plainTimer = null;
        if (stopped || text === skipPlain) return;
        options.onEvent({ type: "committed", text, startMs: null, endMs: null, words: [] });
      }, 40);
      return;
    }
    if (event === null) return;
    if (plainTimer !== null && event.type === "committed") {
      window.clearTimeout(plainTimer);
      plainTimer = null;
    }
    options.onEvent(event);
  });

  socket.addEventListener("close", () => {
    if (stopped) return;
    stopped = true;
    releaseAudio(stream, source, processor, context);
    options.onEvent({ type: "disconnected" });
  });

  return {
    mute() {
      muted = true;
      setTracksEnabled(stream, false);
    },
    unmute() {
      muted = false;
      setTracksEnabled(stream, true);
    },
    stop() {
      if (stopped) return;
      stopped = true;
      if (plainTimer !== null) window.clearTimeout(plainTimer);
      releaseAudio(stream, source, processor, context);
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) socket.close();
    },
  };
}

// Query values come from the public config. commit_strategy=vad is required, not the manual default.
function scribeUrl(options: ScribeConnectOptions): string {
  const params = new URLSearchParams({
    model_id: options.modelId,
    token: options.token,
    commit_strategy: "vad",
    vad_silence_threshold_secs: String(options.vadSilenceSecs),
    vad_threshold: String(options.vadThreshold),
    include_timestamps: options.includeTimestamps ? "true" : "false",
    audio_format: "pcm_16000",
  });
  return `${SCRIBE_URL}?${params.toString()}`;
}

// Resolves once the socket can take audio. An error before that is a failed connection.
function waitUntilOpen(socket: WebSocket): Promise<void> {
  return new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve(), { once: true });
    socket.addEventListener(
      "error",
      () => reject(new Error("The transcription service could not be reached.")),
      { once: true },
    );
  });
}

// Mute keeps the socket up and stops the browser from capturing.
function setTracksEnabled(stream: MediaStream, enabled: boolean) {
  for (const track of stream.getAudioTracks()) track.enabled = enabled;
}

// Ends the microphone so the browser prompt's indicator turns off.
function stopTracks(stream: MediaStream) {
  for (const track of stream.getTracks()) track.stop();
}

// Drops the mic, the processor, and the audio context together.
function releaseAudio(
  stream: MediaStream,
  source: MediaStreamAudioSourceNode,
  processor: ScriptProcessorNode,
  context: AudioContext,
) {
  processor.disconnect();
  source.disconnect();
  stopTracks(stream);
  void context.close();
}

// Reads the transcript string from a server payload, or empty when the field is missing.
function textOf(payload: unknown): string {
  if (typeof payload !== "object" || payload === null || !("text" in payload)) return "";
  const text = payload.text;
  return typeof text === "string" ? text : "";
}

// Maps one server payload to an event. "hold-plain" means a timestamp message may still arrive.
function readServerEvent(
  payload: unknown,
  currentSkip: () => string,
  remember: (text: string) => void,
): ScribeEvent | "hold-plain" | null {
  if (typeof payload !== "object" || payload === null || !("message_type" in payload)) return null;
  const kind = payload.message_type;
  const text = textOf(payload);
  if (kind === "partial_transcript") return { type: "partial", text };
  if (kind === "committed_transcript_with_timestamps") {
    remember(text);
    const words = wordsFrom(payload);
    return {
      type: "committed",
      text,
      words,
      startMs: words[0]?.startMs ?? null,
      endMs: words.length > 0 ? words[words.length - 1].endMs : null,
    };
  }
  if (kind === "committed_transcript") {
    if (text === currentSkip()) return null;
    return "hold-plain";
  }
  if (kind === "auth_error" || kind === "session_time_limit_exceeded") return { type: "token_expired" };
  if (kind === "error" || (typeof kind === "string" && kind.endsWith("_error"))) {
    const message = "error" in payload && typeof payload.error === "string" ? payload.error : "The transcription service reported an error.";
    return { type: "error", message };
  }
  return null;
}

// Keeps word rows and drops spacing tokens. Times are converted to milliseconds.
function wordsFrom(payload: object): ScribeWord[] {
  if (!("words" in payload) || !Array.isArray(payload.words)) return [];
  const words: ScribeWord[] = [];
  for (const item of payload.words) {
    if (typeof item !== "object" || item === null) continue;
    if (!("text" in item) || typeof item.text !== "string") continue;
    if ("type" in item && item.type === "spacing") continue;
    if (!("start" in item) || typeof item.start !== "number") continue;
    if (!("end" in item) || typeof item.end !== "number") continue;
    // Scribe reports seconds. The encounter stores milliseconds.
    words.push({ text: item.text, startMs: Math.round(item.start * 1000), endMs: Math.round(item.end * 1000) });
  }
  return words;
}

// Picks samples down to 16 kHz PCM, which is the format named on the socket.
function downsampleToPcm16(samples: Float32Array, fromRate: number, toRate: number): Int16Array {
  if (fromRate === toRate) return floatToPcm16(samples);
  const ratio = fromRate / toRate;
  const length = Math.max(1, Math.floor(samples.length / ratio));
  const picked = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    picked[index] = samples[Math.min(samples.length - 1, Math.floor(index * ratio))] ?? 0;
  }
  return floatToPcm16(picked);
}

// Converts float samples in -1..1 to the 16-bit integers Scribe expects.
function floatToPcm16(samples: Float32Array): Int16Array {
  const pcm = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[index] ?? 0));
    pcm[index] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return pcm;
}

// Encodes PCM bytes as base64 for one input_audio_chunk message.
function pcm16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index] ?? 0);
  return btoa(binary);
}
