// The Scribe boundary the encounter talks to. Tests pass a fake. The live
// module opens the real ElevenLabs socket. Neither path is a text box.

export type ScribeWord = {
  text: string;
  startMs: number;
  endMs: number;
};

export type ScribeEvent =
  | { type: "partial"; text: string }
  | { type: "committed"; text: string; startMs: number | null; endMs: number | null; words: ScribeWord[] }
  | { type: "disconnected" }
  | { type: "token_expired" }
  | { type: "error"; message: string };

export type ScribeSession = {
  // Privacy mute keeps the socket open and stops microphone audio.
  mute: () => void;
  unmute: () => void;
  // End or leave. Closes the socket and the microphone.
  stop: () => void;
};

export type ScribeConnectOptions = {
  token: string;
  modelId: string;
  vadSilenceSecs: number;
  vadThreshold: number;
  echoCancellation: true;
  noiseSuppression: true;
  includeTimestamps: boolean;
  onEvent: (event: ScribeEvent) => void;
};

export type ScribeConnector = (options: ScribeConnectOptions) => Promise<ScribeSession>;

// Stops audio elements this page already started. Streamed speech is a later ticket.
export function stopOwnedAudio(): void {
  document.querySelectorAll("audio").forEach((element) => {
    if (element instanceof HTMLAudioElement) element.pause();
  });
}
