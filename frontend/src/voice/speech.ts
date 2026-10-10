// Patient speech playback. The bytes are the saved verified reply, already checked
// by the server. This file only plays them, or names the browser voice when it speaks.

export type SpeechSource = {
  // The next audio chunk, or null when the vendor stream has ended.
  read: () => Promise<Uint8Array | null>;
  // Stop reading. This also drops the upstream response.
  cancel: () => void;
};

export type PlaybackHooks = {
  // Fires when the player starts. That is later than the first bytes being read.
  onFirstPlayback?: () => void;
};

export type SpeechPlayback = {
  // Start as soon as a chunk can be played. Do not wait for the rest of the stream.
  play: (source: SpeechSource, hooks?: PlaybackHooks) => Promise<void>;
  stop: () => void;
  // Milliseconds of audio still left, only when the browser actually knows.
  remainingMs: () => number | undefined;
};

export type BrowserVoice = {
  provider: "browser";
  speak: (text: string) => void;
  cancel: () => void;
};

// Wraps one response body so playback can stop it without reading the rest first.
export function verifiedAudioSource(body: ReadableStream<Uint8Array>, controller: AbortController): SpeechSource {
  const reader = body.getReader();
  return {
    async read() {
      const next = await reader.read();
      if (next.done) return null;
      return next.value;
    },
    cancel() {
      try {
        controller.abort();
      } catch {
        // Abort listeners can fail when the body is already being read. The reader cancel still runs.
      }
      // Cancelling the reader tells the server the rest of the audio is not needed.
      void reader.cancel().catch(() => undefined);
    },
  };
}

// Notes the first audio bytes without treating that read as playback.
export function observeFirstAudioByte(source: SpeechSource, onFirstByte: () => void): SpeechSource {
  let seen = false;
  return {
    async read() {
      const chunk = await source.read();
      // An empty chunk is not audio yet. Wait for bytes the player can use.
      if (chunk && chunk.byteLength > 0 && !seen) {
        seen = true;
        onFirstByte();
      }
      return chunk;
    },
    cancel() {
      source.cancel();
    },
  };
}

// The fallback voice. The provider name is the browser, because that is what speaks.
export function createBrowserVoice(): BrowserVoice {
  return {
    provider: "browser",
    speak(text: string) {
      const synth = window.speechSynthesis;
      if (!synth || typeof SpeechSynthesisUtterance === "undefined") return;
      const utterance = new SpeechSynthesisUtterance(text);
      synth.cancel();
      synth.speak(utterance);
    },
    cancel() {
      window.speechSynthesis?.cancel();
    },
  };
}

// Plays MPEG chunks with Media Source when the browser supports that type.
export function createMpegPlayback(provided?: HTMLAudioElement): SpeechPlayback {
  let audio = provided ?? null;
  let current: SpeechSource | null = null;
  let stopped = false;
  let objectUrl = "";

  // The element is created on first play so tests that never speak do not need one.
  function element(): HTMLAudioElement {
    if (!audio) audio = new Audio();
    return audio;
  }

  return {
    async play(source: SpeechSource, hooks?: PlaybackHooks) {
      stopped = false;
      current = source;
      const Media = globalThis.MediaSource;
      if (typeof Media === "undefined" || !Media.isTypeSupported("audio/mpeg")) {
        throw new Error("This browser cannot play streamed audio.");
      }
      const media = new Media();
      const player = element();
      objectUrl = URL.createObjectURL(media);
      player.src = objectUrl;
      await waitUntilOpen(media);
      const buffer = media.addSourceBuffer("audio/mpeg");
      let started = false;
      while (!stopped) {
        let chunk: Uint8Array | null;
        try {
          chunk = await source.read();
        } catch {
          // Cancellation rejects the read. Stopping is not a playback failure.
          break;
        }
        if (chunk === null || stopped) break;
        await appendChunk(buffer, chunk);
        if (!started) {
          started = true;
          // The first chunk is enough to start. Later chunks append while it plays.
          await player.play();
          // Playback is this start, not the earlier read that delivered the bytes.
          hooks?.onFirstPlayback?.();
        }
      }
      if (!stopped && media.readyState === "open") media.endOfStream();
    },
    stop() {
      stopped = true;
      current?.cancel();
      current = null;
      if (!audio) return;
      audio.pause();
      if (objectUrl) {
        const url = objectUrl;
        objectUrl = "";
        audio.removeAttribute("src");
        audio.load();
        URL.revokeObjectURL(url);
      }
    },
    remainingMs() {
      if (!audio) return undefined;
      // An unknown duration is not a sentence boundary, so it is left unrecorded.
      if (!Number.isFinite(audio.duration)) return undefined;
      const remaining = Math.round((audio.duration - audio.currentTime) * 1000);
      if (!Number.isFinite(remaining)) return undefined;
      return Math.max(0, remaining);
    },
  };
}

// Resolves when the media element can take a buffer. Already-open sources resolve at once.
function waitUntilOpen(media: MediaSource): Promise<void> {
  if (media.readyState === "open") return Promise.resolve();
  return new Promise((resolve) => {
    media.addEventListener("sourceopen", () => resolve(), { once: true });
  });
}

// Waits until this chunk is in the buffer. The next read can happen after that.
function appendChunk(buffer: SourceBuffer, chunk: Uint8Array): Promise<void> {
  return new Promise((resolve, reject) => {
    const done = () => {
      buffer.removeEventListener("updateend", done);
      buffer.removeEventListener("error", fail);
      resolve();
    };
    const fail = () => {
      buffer.removeEventListener("updateend", done);
      buffer.removeEventListener("error", fail);
      reject(new Error("The reply could not be played."));
    };
    buffer.addEventListener("updateend", done);
    buffer.addEventListener("error", fail);
    // Copy into a plain buffer. A shared buffer is not a valid media source chunk.
    const copy = new Uint8Array(chunk.byteLength);
    copy.set(chunk);
    buffer.appendBuffer(copy);
  });
}
