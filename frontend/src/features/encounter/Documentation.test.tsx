import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import { createApi, type ApiClient } from "../../api/client";
import type { Go } from "../../app/types";
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

const template = {
  id: "PES" as const,
  label: "PES statement (Problem, Etiology, Signs and symptoms)",
  fields: [
    { id: "problem", label: "Problem", hint: "The nutrition diagnosis" },
    { id: "etiology", label: "Etiology", hint: "Related to: the cause" },
    { id: "signs", label: "Signs and symptoms", hint: "As evidenced by: what you found" },
  ],
};

const activeEncounter = {
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
  chart: [],
  transcript: [
    {
      turn: 1,
      student_text: "Do you take anything over the counter for pain?",
      reply_text: "Advil for my back.",
      mode: "template" as const,
      is_last: true,
    },
  ],
  started_at: "2026-10-10T15:00:00Z",
  ended_at: null,
  last_turn: 1,
  documentation_template: template,
  saved_documentation: null,
};

const endedEncounter = {
  ...activeEncounter,
  status: "ended" as const,
  ended_at: "2026-10-10T15:20:00Z",
};

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

type Call = { url: string; method: string; body: unknown };

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

// Records each call the shared client makes.
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
  connects = 0;
  stops = 0;
  fail: Error | null = null;
  private handler: ((event: ScribeEvent) => void) | null = null;

  // Each connect is a new capture. The note test checks that ending the visit does not reuse this one.
  connect = async (options: ScribeConnectOptions): Promise<ScribeSession> => {
    this.connects += 1;
    if (this.fail) throw this.fail;
    this.options = options;
    this.handler = options.onEvent;
    return {
      mute: () => undefined,
      unmute: () => undefined,
      stop: () => {
        this.stops += 1;
      },
    };
  };

  emit(event: ScribeEvent) {
    this.handler?.(event);
  }
}

async function renderEncounter(
  client: ApiClient,
  scribe: FakeScribe,
  go: Go = () => undefined,
  stopOwnedAudio: () => void = () => undefined,
) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<Encounter route={route} client={client} connectScribe={scribe.connect} stopOwnedAudio={stopOwnedAudio} go={go} />);
  });
  return container;
}

function buttonNamed(container: HTMLElement, name: string): HTMLButtonElement {
  const found = [...container.querySelectorAll("button")].find((button) => button.textContent?.trim() === name);
  if (!found) throw new Error(`No button named ${name}. Saw: ${[...container.querySelectorAll("button")].map((button) => button.textContent?.trim()).join(" | ")}`);
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

test("ending stops the visit mic, then dictation uses a new session and submits the reviewed note", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, activeEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_note" });
    if (method === "POST" && url.endsWith("/end")) return jsonResponse(200, endedEncounter);
    if (method === "POST" && url.endsWith("/documentation")) return jsonResponse(200, { ok: true });
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  let audioStops = 0;
  const screens: string[] = [];
  const container = await renderEncounter(seen.client, scribe, (screen) => {
    screens.push(screen);
  }, () => {
    audioStops += 1;
  });

  expect(container.textContent).not.toContain("Dictate Problem");
  expect(container.textContent).not.toContain("Trust");
  expect(container.querySelector("textarea, input")).toBeNull();

  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  expect(scribe.connects).toBe(1);

  await click(buttonNamed(container, "End visit"));
  await settle();
  expect(scribe.stops).toBeGreaterThanOrEqual(1);
  expect(audioStops).toBe(1);
  expect(container.textContent).toContain("PES statement (Problem, Etiology, Signs and symptoms)");
  expect(container.textContent).toContain("The nutrition diagnosis");
  expect(container.textContent).toContain("Nothing dictated yet.");
  expect(container.textContent).not.toContain("Trust");
  expect(container.querySelector("textarea, input")).toBeNull();
  expect(seen.calls.some((call) => call.method === "POST" && call.url.endsWith("/api/encounters"))).toBe(false);

  await click(buttonNamed(container, "Dictate Problem"));
  await settle();
  expect(scribe.connects).toBe(2);
  expect(scribe.options?.token).toBe("sutkn_note");
  expect(container.textContent).toContain("Dictating Problem");

  await act(async () => {
    scribe.emit({ type: "partial", text: "excess" });
  });
  expect(container.textContent).toContain("excess");
  expect(seen.calls.some((call) => call.url.endsWith("/utterances"))).toBe(false);

  await act(async () => {
    scribe.emit({
      type: "committed",
      text: "Excess sodium at dinner club.",
      startMs: 0,
      endMs: 1000,
      words: [],
    });
  });
  expect(container.textContent).toContain("Excess sodium at dinner club.");
  expect(container.textContent).not.toContain("This note was submitted.");

  await click(buttonNamed(container, "Submit documentation"));
  await settle();
  const submitted = seen.calls.find((call) => call.method === "POST" && call.url.endsWith("/documentation"));
  expect(submitted?.body).toEqual({
    fields: {
      problem: "Excess sodium at dinner club.",
      etiology: "",
      signs: "",
    },
  });
  expect(screens).toEqual(["s-debrief"]);
  expect(container.textContent).toContain("This note was submitted.");
  expect(seen.calls.some((call) => call.url.endsWith("/utterances"))).toBe(false);
});

test("missing voice configuration stays visible and does not look finished", async () => {
  const missing = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, endedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) {
      return jsonResponse(409, { message: "Speech transcription is not configured.", errors: [], blockers: [] });
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const missingView = await renderEncounter(missing.client, scribe);
  expect(missing.calls.some((call) => call.method === "POST" && call.url.endsWith("/api/encounters"))).toBe(false);
  expect(missingView.textContent).toContain("Dictate Problem");
  await click(buttonNamed(missingView, "Dictate Problem"));
  await settle();
  expect(scribe.connects).toBe(0);
  expect(missingView.textContent).toContain("Speech transcription is not configured.");
  expect(missingView.textContent).not.toContain("This note was submitted.");
});

test("a failed submit keeps the dictated note on screen", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, endedEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_note" });
    if (method === "POST" && url.endsWith("/documentation")) {
      return jsonResponse(503, { message: "Documentation could not be saved.", errors: [], blockers: [] });
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const screens: string[] = [];
  const container = await renderEncounter(seen.client, scribe, (screen) => {
    screens.push(screen);
  });
  await click(buttonNamed(container, "Dictate Problem"));
  await settle();
  await act(async () => {
    scribe.emit({
      type: "committed",
      text: "Excess sodium at dinner club.",
      startMs: null,
      endMs: null,
      words: [],
    });
  });
  await click(buttonNamed(container, "Submit documentation"));
  await settle();
  expect(container.textContent).toContain("Documentation could not be saved.");
  expect(container.textContent).toContain("Excess sodium at dinner club.");
  expect(container.textContent).not.toContain("This note was submitted.");
  expect(screens).toEqual([]);
  expect(container.textContent).toContain("Submit documentation");
});

test("an ended or complete encounter reopens without starting another one", async () => {
  const ended = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, endedEncounter);
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const endedView = await renderEncounter(ended.client, new FakeScribe());
  expect(ended.calls.map((call) => `${call.method} ${call.url}`)).toEqual(["GET http://voice.test/api/encounters/enc_1"]);
  expect(endedView.textContent).toContain("Dictate Problem");
  expect(endedView.textContent).not.toContain("Connect microphone");

  const completeEncounter = {
    ...endedEncounter,
    status: "complete" as const,
    saved_documentation: { problem: "Excess sodium at dinner club.", etiology: "", signs: "" },
  };
  const screens: string[] = [];
  const complete = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, completeEncounter);
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const completeView = await renderEncounter(complete.client, new FakeScribe(), (screen) => {
    screens.push(screen);
  });
  expect(complete.calls.some((call) => call.method === "POST")).toBe(false);
  expect(completeView.textContent).toContain("This note was submitted.");
  expect(completeView.textContent).toContain("Excess sodium at dinner club.");
  expect(completeView.textContent).not.toContain("Dictate Problem");
  await click(buttonNamed(completeView, "Open debrief"));
  expect(screens).toEqual(["s-debrief"]);
});

test("a failed end stays on the visit and does not open the note", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, activeEncounter);
    if (method === "GET" && url.endsWith("/api/config")) return jsonResponse(200, voiceConfig);
    if (method === "POST" && url.endsWith("/api/stt/token")) return jsonResponse(200, { token: "sutkn_visit" });
    if (method === "POST" && url.endsWith("/end")) {
      return jsonResponse(503, { message: "The encounter could not be ended.", errors: [], blockers: [] });
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });
  const scribe = new FakeScribe();
  const container = await renderEncounter(seen.client, scribe);
  await click(buttonNamed(container, "Connect microphone"));
  await settle();
  await click(buttonNamed(container, "End visit"));
  await settle();
  expect(container.textContent).toContain("The encounter could not be ended.");
  expect(container.textContent).not.toContain("Dictate Problem");
  expect(container.textContent).not.toContain("This note was submitted.");
  expect(scribe.stops).toBeGreaterThanOrEqual(1);
});
