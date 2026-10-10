import { expect, test } from "bun:test";
import { createMpegPlayback, observeFirstAudioByte, verifiedAudioSource, type SpeechSource } from "./speech";

// A browser stand-in. It records play() and accepts the chunks a real buffer would.
function installMediaSource() {
  const appended: Uint8Array[] = [];

  // A tiny event target. The DOM Event constructor and the platform EventTarget do not always match.
  class ListenerList {
    private listeners = new Map<string, Array<() => void>>();

    addEventListener(type: string, fn: () => void, options?: { once?: boolean }) {
      const wrapped = () => {
        if (options?.once) this.removeEventListener(type, wrapped);
        fn();
      };
      const list = this.listeners.get(type) ?? [];
      list.push(wrapped);
      this.listeners.set(type, list);
    }

    removeEventListener(type: string, fn: () => void) {
      const list = this.listeners.get(type) ?? [];
      this.listeners.set(
        type,
        list.filter((item) => item !== fn),
      );
    }

    emit(type: string) {
      for (const fn of [...(this.listeners.get(type) ?? [])]) fn();
    }
  }

  class FakeBuffer extends ListenerList {
    updating = false;

    // The player waits for updateend, so this finishes on the next turn.
    appendBuffer(chunk: Uint8Array) {
      appended.push(chunk);
      this.updating = true;
      queueMicrotask(() => {
        this.updating = false;
        this.emit("updateend");
      });
    }
  }

  class FakeMediaSource extends ListenerList {
    readyState = "closed";
    sourceBuffers = { length: 0 };

    constructor() {
      super();
      queueMicrotask(() => {
        this.readyState = "open";
        this.emit("sourceopen");
      });
    }

    addSourceBuffer() {
      return new FakeBuffer();
    }

    endOfStream() {
      this.readyState = "ended";
    }

    static isTypeSupported(type: string) {
      return type === "audio/mpeg";
    }
  }

  const previous = globalThis.MediaSource;
  const previousCreate = URL.createObjectURL;
  const previousRevoke = URL.revokeObjectURL;
  globalThis.MediaSource = FakeMediaSource as unknown as typeof MediaSource;
  URL.createObjectURL = () => "blob:verified-speech";
  URL.revokeObjectURL = () => undefined;
  return {
    appended,
    restore() {
      globalThis.MediaSource = previous;
      URL.createObjectURL = previousCreate;
      URL.revokeObjectURL = previousRevoke;
    },
  };
}

function fakeAudio() {
  let plays = 0;
  return {
    src: "",
    currentTime: 1,
    duration: Number.NaN,
    paused: true,
    async play() {
      plays += 1;
      this.paused = false;
    },
    pause() {
      this.paused = true;
    },
    removeAttribute() {
      this.src = "";
    },
    load() {
      return undefined;
    },
    get plays() {
      return plays;
    },
  };
}

// Holds the second chunk until the test lets it go, or until the stream is cancelled.
function delayedStream() {
  let release: () => void = () => undefined;
  const hold = new Promise<void>((resolve) => {
    release = resolve;
  });
  let sentSecond = false;
  let cancelled = false;
  let sentFirst = false;
  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
      if (!sentFirst) {
        sentFirst = true;
        controller.enqueue(new Uint8Array([9, 8, 7]));
        return;
      }
      await hold;
      if (cancelled) {
        controller.close();
        return;
      }
      sentSecond = true;
      controller.enqueue(new Uint8Array([1]));
      controller.close();
    },
    cancel() {
      cancelled = true;
      release();
    },
  });
  const source: SpeechSource = verifiedAudioSource(stream, new AbortController());
  return {
    source,
    get sentSecond() {
      return sentSecond;
    },
    get cancelled() {
      return cancelled;
    },
  };
}

test("playback starts on the first chunk and cancellation releases the stream", async () => {
  const media = installMediaSource();
  const audio = fakeAudio();
  const playback = createMpegPlayback(audio as unknown as HTMLAudioElement);
  const delayed = delayedStream();

  const playing = playback.play(delayed.source);
  const started = Date.now();
  while (audio.plays === 0) {
    if (Date.now() - started > 500) throw new Error("playback waited for the full response");
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  expect(Array.from(media.appended[0] ?? [])).toEqual([9, 8, 7]);
  expect(delayed.sentSecond).toBe(false);
  expect(delayed.cancelled).toBe(false);
  expect(playback.remainingMs()).toBeUndefined();

  playback.stop();
  await playing;

  expect(delayed.cancelled).toBe(true);
  expect(delayed.sentSecond).toBe(false);
  expect(audio.paused).toBe(true);
  media.restore();
});

test("first playback is reported when audio starts, after the first bytes were read", async () => {
  const media = installMediaSource();
  const audio = fakeAudio();
  const playback = createMpegPlayback(audio as unknown as HTMLAudioElement);
  const delayed = delayedStream();
  let bytes = 0;
  let playbacksAtPlay = 0;

  const playing = playback.play(
    observeFirstAudioByte(delayed.source, () => {
      bytes += 1;
    }),
    {
      onFirstPlayback() {
        // The player has started. A byte callback alone is not this event.
        playbacksAtPlay = audio.plays;
      },
    },
  );
  const started = Date.now();
  while (audio.plays === 0) {
    if (Date.now() - started > 500) throw new Error("playback waited for the full response");
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  expect(bytes).toBe(1);
  expect(playbacksAtPlay).toBe(1);
  playback.stop();
  await playing;
  media.restore();
});
