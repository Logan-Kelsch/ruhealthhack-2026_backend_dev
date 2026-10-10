import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import { createApi, type ApiClient } from "../../api/client";
import type { StudentRoute } from "../../app/types";
import { Encounter } from "./Encounter";
import type { ScribeConnectOptions, ScribeEvent, ScribeSession } from "../../voice/scribe";

const route: StudentRoute = {
  caseId: "walter_greene",
  version: 1,
  visitId: "v1",
  encounterId: "enc_1",
};

const voiceConfig = {
  llm: false,
  tts: false,
  stt_provider: "elevenlabs" as const,
  stt_model_id: "scribe_v2_realtime",
  voice_id: "voice_public_demo",
  tts_model_id: "eleven_turbo_v2_5",
  vad_silence_secs: 1.2,
  vad_threshold: 0.4,
  commit_strategy: "vad" as const,
  include_timestamps: true,
};

const savedEncounter = {
  encounter_id: "enc_1",
  status: "active" as const,
  case_id: "walter_greene",
  case_version: 1,
  visit_id: "v1",
  visit_label: "First visit",
  has_next_visit: true,
  previous_encounter_id: null,
  patient: {
    name: "Walter Greene",
    age: 72,
    sex: "male" as const,
    pronouns: "he/him",
    portrait: null,
    speaker: "Walter Greene",
  },
  briefing: {
    setting: "Outpatient nutrition clinic",
    reason_for_visit: "Referral",
    goal: "Take a nutrition-focused history",
    student_role: "Dietetics student",
    show_doorway_vitals: true,
  },
  chart: [
    {
      kind: "artifact" as const,
      ref: "referral",
      label: "Referral from primary care",
      body: "Medical nutrition therapy referral.",
      source: { kind: "faculty" as const, ref: null },
    },
  ],
  transcript: [],
  started_at: "2026-10-10T15:00:00Z",
  ended_at: null,
  last_turn: null,
};

const ibuprofenTurn = {
  turn: 1,
  reply_text: "I take ibuprofen for my back.",
  speaker: "Walter Greene",
  audio_tags: [],
  chart_releases: [
    {
      kind: "medication" as const,
      ref: "Ibuprofen",
      label: "Ibuprofen",
      value: "200 mg",
      section: "Medications",
      source_fact: "f_ibuprofen",
      source: { kind: "faculty" as const, ref: null },
    },
  ],
  exam_results: [],
  notices: [{ kind: "fallback" as const, text: "Simplified responses" }],
  mode: "template" as const,
  latency_ms: {},
};

const lungTurn = {
  turn: 2,
  reply_text: "Okay, go ahead.",
  speaker: "Walter Greene",
  audio_tags: [],
  chart_releases: [],
  exam_results: [
    {
      kind: "exam" as const,
      ref: "lung_auscultation",
      label: "Lung auscultation",
      value: "Fine crackles at both lung bases.",
      section: "Exam",
      source: { kind: "faculty" as const, ref: null },
    },
  ],
  notices: [{ kind: "fallback" as const, text: "Simplified responses" }],
  mode: "template" as const,
  latency_ms: {},
};

type Call = { url: string; method: string; body: unknown };

const mounts: Root[] = [];

afterEach(() => {
  for (const root of mounts) {
    act(() => root.unmount());
  }
  mounts.length = 0;
  document.body.innerHTML = "";
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

// Records each API call. The handler decides the response for that URL.
function installFetch(handler: (url: string, method: string, body: unknown) => Promise<Response> | Response) {
  const calls: Call[] = [];
  const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    const method = init?.method ?? (input instanceof Request ? input.method : "GET");
    let raw = typeof init?.body === "string" ? init.body : "";
    if (!raw && input instanceof Request) raw = await input.clone().text();
    const body = raw ? JSON.parse(raw) : null;
    calls.push({ url, method, body });
    return handler(url, method, body);
  };
  return { calls, client: createApi("http://voice.test", fetchImpl as typeof fetch) };
}

class FakeScribe {
  options: ScribeConnectOptions | null = null;
  muted = false;
  stopped = false;
  connects = 0;
  fail: Error | null = null;
  private handler: ((event: ScribeEvent) => void) | null = null;

  // The encounter asks for a session. This records the options and returns controls the test can watch.
  connect = async (options: ScribeConnectOptions): Promise<ScribeSession> => {
    this.connects += 1;
    if (this.fail) throw this.fail;
    this.options = options;
    this.handler = options.onEvent;
    this.stopped = false;
    this.muted = false;
    return {
      mute: () => {
        this.muted = true;
      },
      unmute: () => {
        this.muted = false;
      },
      stop: () => {
        this.stopped = true;
      },
    };
  };

  // Delivers one provider event, the way Scribe would after a socket message.
  emit(event: ScribeEvent) {
    this.handler?.(event);
  }
}

async function renderEncounter(client: ApiClient, scribe: FakeScribe, stopOwnedAudio: () => void = () => {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(
      <Encounter route={route} client={client} connectScribe={scribe.connect} stopOwnedAudio={stopOwnedAudio} />,
    );
  });
  return container;
}

function buttonNamed(container: HTMLElement, name: string): HTMLButtonElement {
  const found = [...container.querySelectorAll("button")].find((button) => button.textContent?.trim() === name);
  if (!found) throw new Error(`No button named ${name}`);
  return found as HTMLButtonElement;
}

async function click(button: HTMLButtonElement) {
  await act(async () => {
    button.click();
  });
}

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function utteranceCalls(calls: Call[]) {
  return calls.filter((call) => call.method === "POST" && call.url.endsWith("/utterances"));
}

function tokenCalls(calls: Call[]) {
  return calls.filter((call) => call.method === "POST" && call.url.endsWith("/api/stt/token"));
}

const painWords = [
  { text: "Do", start_ms: 1200, end_ms: 1400 },
  { text: "ibuprofen", start_ms: 1500, end_ms: 1800 },
];

function committedPain(): ScribeEvent {
  return {
    type: "committed",
    text: "Do you take ibuprofen?",
    startMs: 1200,
    endMs: 1800,
    words: [
      { text: "Do", startMs: 1200, endMs: 1400 },
      { text: "ibuprofen", startMs: 1500, endMs: 1800 },
    ],
  };
}

test("partial captions stay local and a committed turn updates the visit", async () => {
  const seen = installFetch((url, method, body) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_test" });
    if (method === "POST" && url.endsWith("/utterances")) {
      expect(body).toEqual({
        text: "Do you take ibuprofen?",
        start_ms: 1200,
        end_ms: 1800,
        words: painWords,
      });
      return jsonResponse(200, ibuprofenTurn);
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const container = await renderEncounter(seen.client, scribe);
  expect(container.textContent).toContain("Walter Greene");
  expect(container.textContent).toContain("Take a nutrition-focused history");
  expect(container.querySelector("textarea")).toBeNull();
  expect(container.querySelector("input")).toBeNull();
  expect(tokenCalls(seen.calls)).toHaveLength(0);

  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  expect(scribe.options).toMatchObject({
    token: "sutkn_test",
    modelId: "scribe_v2_realtime",
    vadSilenceSecs: 1.2,
    vadThreshold: 0.4,
    echoCancellation: true,
    noiseSuppression: true,
    includeTimestamps: true,
  });
  expect(container.textContent).toContain("Headphones recommended");
  expect(container.textContent).toContain("Microphone live");

  await act(async () => {
    scribe.emit({ type: "partial", text: "hmm maybe pain meds" });
  });
  expect(container.textContent).toContain("hmm maybe pain meds");
  expect(utteranceCalls(seen.calls)).toHaveLength(0);

  await act(async () => {
    scribe.emit(committedPain());
  });
  await settle();
  expect(utteranceCalls(seen.calls)).toHaveLength(1);
  expect(container.textContent).toContain("Do you take ibuprofen?");
  expect(container.textContent).toContain("I take ibuprofen for my back.");
  expect(container.textContent).toContain("Fact f_ibuprofen");
  expect(container.textContent).toContain("Source: faculty");
  expect(container.textContent).toContain("Simplified responses");
  expect(container.textContent).not.toContain("Trust");
  expect(container.textContent).not.toContain("hmm maybe pain meds");
});

test("committed turns are submitted one at a time", async () => {
  let release: (response: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  let posts = 0;
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_test" });
    if (method === "POST" && url.endsWith("/utterances")) {
      posts += 1;
      if (posts === 1) return pending;
      return jsonResponse(200, lungTurn);
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const container = await renderEncounter(seen.client, scribe);
  await click(buttonNamed(container, "Connect microphone"));
  await settle();

  await act(async () => {
    scribe.emit(committedPain());
    scribe.emit({
      type: "committed",
      text: "I'm going to listen to your lungs.",
      startMs: 5000,
      endMs: 7000,
      words: [],
    });
  });
  expect(utteranceCalls(seen.calls)).toHaveLength(1);
  expect(utteranceCalls(seen.calls)[0]?.body).toMatchObject({ text: "Do you take ibuprofen?" });

  await act(async () => {
    release(jsonResponse(200, ibuprofenTurn));
  });
  await settle();
  expect(utteranceCalls(seen.calls).map((call) => (call.body as { text: string }).text)).toEqual([
    "Do you take ibuprofen?",
    "I'm going to listen to your lungs.",
  ]);
  expect(container.textContent).toContain("I take ibuprofen for my back.");
  expect(container.textContent).toContain("Fine crackles at both lung bases.");
  expect(container.textContent).toContain("Okay, go ahead.");
});

test("mute drops speech and unmute submits the next commit", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_test" });
    if (method === "POST" && url.endsWith("/utterances")) return jsonResponse(200, ibuprofenTurn);
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const container = await renderEncounter(seen.client, scribe);
  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  await click(buttonNamed(container, "Mute microphone"));
  expect(scribe.muted).toBe(true);
  expect(container.textContent).toContain("Microphone muted");

  await act(async () => {
    scribe.emit({ type: "partial", text: "secret words" });
    scribe.emit(committedPain());
  });
  await settle();
  expect(container.textContent).not.toContain("secret words");
  expect(utteranceCalls(seen.calls)).toHaveLength(0);

  await click(buttonNamed(container, "Unmute microphone"));
  expect(scribe.muted).toBe(false);
  await act(async () => {
    scribe.emit(committedPain());
  });
  await settle();
  expect(utteranceCalls(seen.calls)).toHaveLength(1);
});

test("permission denial and missing configuration stay on screen", async () => {
  const denied = new FakeScribe();
  denied.fail = Object.assign(new Error("denied"), { name: "NotAllowedError" });
  const deniedFetch = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_test" });
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const deniedView = await renderEncounter(deniedFetch.client, denied);
  await click(buttonNamed(deniedView, "Connect microphone"));
  await settle();
  expect(deniedView.textContent).toContain("Microphone permission was denied.");
  expect(deniedView.querySelector("textarea")).toBeNull();

  const missing = new FakeScribe();
  const missingFetch = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) {
      return jsonResponse(409, { message: "Speech transcription is not configured.", errors: [], blockers: [] });
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const missingView = await renderEncounter(missingFetch.client, missing);
  await click(buttonNamed(missingView, "Connect microphone"));
  await settle();
  expect(missingView.textContent).toContain("Speech transcription is not configured.");
  expect(missing.connects).toBe(0);
});

test("token expiry and provider disconnection ask for a new connection", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_next" });
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const container = await renderEncounter(seen.client, scribe);
  await click(buttonNamed(container, "Connect microphone"));
  await settle();

  await act(async () => {
    scribe.emit({ type: "token_expired" });
  });
  expect(container.textContent).toContain("The transcription token expired. Connect the microphone again.");
  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  expect(tokenCalls(seen.calls)).toHaveLength(2);
  expect(scribe.options?.token).toBe("sutkn_next");

  await act(async () => {
    scribe.emit({ type: "disconnected" });
  });
  expect(container.textContent).toContain("The transcription service disconnected. Connect the microphone again.");
});

test("a failed turn shows the error and is not sent again", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_test" });
    if (method === "POST" && url.endsWith("/utterances")) {
      return jsonResponse(409, { message: "This encounter has ended.", errors: [], blockers: [] });
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const container = await renderEncounter(seen.client, scribe);
  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  await act(async () => {
    scribe.emit(committedPain());
  });
  await settle();
  expect(container.textContent).toContain("This encounter has ended.");
  expect(utteranceCalls(seen.calls)).toHaveLength(1);
  expect(container.textContent).not.toContain("I take ibuprofen for my back.");
});

test("ending or leaving stops capture, queued turns, and owned audio", async () => {
  let release: (response: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, savedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_test" });
    if (method === "POST" && url.endsWith("/utterances")) return pending;
    if (method === "POST" && url.endsWith("/end")) return jsonResponse(200, { ...savedEncounter, status: "ended" });
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  let audioStops = 0;
  const container = await renderEncounter(seen.client, scribe, () => {
    audioStops += 1;
  });
  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  await act(async () => {
    scribe.emit(committedPain());
    scribe.emit({
      type: "committed",
      text: "I'm going to listen to your lungs.",
      startMs: 5000,
      endMs: 7000,
      words: [],
    });
  });
  expect(utteranceCalls(seen.calls)).toHaveLength(1);

  await click(buttonNamed(container, "End visit"));
  expect(scribe.stopped).toBe(true);
  expect(audioStops).toBe(1);
  await act(async () => {
    release(jsonResponse(200, ibuprofenTurn));
  });
  await settle();
  expect(utteranceCalls(seen.calls)).toHaveLength(1);
  expect(seen.calls.some((call) => call.method === "POST" && call.url.endsWith("/end"))).toBe(true);

  await act(async () => {
    mounts.at(-1)?.unmount();
  });
  expect(audioStops).toBe(2);
  expect(scribe.stopped).toBe(true);
});

test("refresh waits for a microphone action and an uncertain turn is not resent", async () => {
  let posts = 0;
  const recovered = {
    ...savedEncounter,
    transcript: [
      {
        turn: 1,
        student_text: "Do you take ibuprofen?",
        reply_text: "I take ibuprofen for my back.",
        student_start_ms: 1200,
        student_end_ms: 1800,
        words: painWords,
        mode: "template" as const,
        is_last: true,
      },
    ],
    last_turn: 1,
    chart: [
      ...(savedEncounter.chart ?? []),
      {
        kind: "medication" as const,
        ref: "Ibuprofen",
        label: "Ibuprofen",
        value: "200 mg",
        section: "Medications",
        source_fact: "f_ibuprofen",
        source: { kind: "faculty" as const, ref: null },
      },
    ],
  };
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) {
      return jsonResponse(200, posts === 0 ? savedEncounter : recovered);
    }
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_fresh" });
    if (method === "POST" && url.endsWith("/utterances")) {
      posts += 1;
      return Promise.reject(new TypeError("network down"));
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const container = await renderEncounter(seen.client, scribe);
  expect(tokenCalls(seen.calls)).toHaveLength(0);
  expect(container.textContent).toContain("Connect microphone");

  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  expect(tokenCalls(seen.calls)).toHaveLength(1);
  expect(scribe.options?.token).toBe("sutkn_fresh");

  await act(async () => {
    scribe.emit(committedPain());
  });
  await settle();
  expect(utteranceCalls(seen.calls)).toHaveLength(1);
  expect(container.textContent).toContain("This turn may not have been saved. The saved visit is shown. It was not sent again.");
  expect(container.textContent).toContain("I take ibuprofen for my back.");
  expect(container.textContent).toContain("Fact f_ibuprofen");
  expect(container.textContent).not.toContain("exactly once");
  expect(seen.calls.filter((call) => call.method === "GET" && call.url.endsWith("/api/encounters/enc_1"))).toHaveLength(2);
});
