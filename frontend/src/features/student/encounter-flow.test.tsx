import { expect, test } from "bun:test";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createApi } from "../../api/client";
import { App } from "../../app/App";

const walterCase = {
  case_id: "walter_greene",
  version: 1,
  title: "Walter Greene: diabetes, heart failure and a dinner club",
  golden: true,
  patient: {
    name: "Walter Greene",
    age: 72,
    sex: "male" as const,
    pronouns: "he/him",
    portrait: "walter_greene.jpg",
    speaker: null,
  },
  briefing: {
    setting: "Outpatient nutrition clinic",
    reason_for_visit: "Referral for medical nutrition therapy: diabetes, heart failure and kidney disease",
    goal: "Take a nutrition-focused history, find what gets in the way of his eating and medicines, and agree on one or two realistic changes.",
    student_role: "Dietetics student (supervised practice)",
    show_doorway_vitals: true,
  },
  visits: [
    { id: "v1", label: "First visit", day: 0 },
    { id: "v2", label: "Follow-up, 3 months later", day: 90 },
  ],
  doorway_vitals: [
    {
      key: "bp",
      label: "Blood pressure",
      value: "158/92",
      unit: "mmHg",
      source: { kind: "faculty" as const, ref: null },
    },
  ],
};

const encounter = {
  encounter_id: "enc-walter",
  status: "active" as const,
  case_id: "walter_greene",
  case_version: 1,
  visit_id: "v1",
  visit_label: "First visit",
  has_next_visit: true,
  previous_encounter_id: null,
  patient: walterCase.patient,
  briefing: walterCase.briefing,
  started_at: "2026-10-10T14:00:00Z",
  ended_at: null,
  last_turn: 2,
  transcript: [
    {
      turn: 1,
      student_text: "Do you take anything over the counter for pain?",
      reply_text: "Advil for my back. Two, three times a week.",
      student_start_ms: 1200,
      student_end_ms: 4600,
      is_last: false,
    },
    {
      turn: 2,
      student_text: "I'm going to listen to your lungs.",
      reply_text: "Okay.",
      student_start_ms: 5000,
      student_end_ms: 7000,
      is_last: true,
    },
  ],
  chart: [
    {
      kind: "vital" as const,
      ref: "bp",
      label: "Blood pressure",
      value: "158/92 mmHg",
      flag: null,
      section: "Vitals",
      source_fact: null,
      source: { kind: "faculty" as const, ref: null },
      body: null,
    },
    {
      kind: "artifact" as const,
      ref: "referral",
      label: "Referral from primary care",
      value: null,
      flag: null,
      section: "Documents",
      source_fact: null,
      source: { kind: "faculty" as const, ref: null },
      body: "Medical nutrition therapy referral. 72-year-old man with uncontrolled type 2 diabetes.",
    },
    {
      kind: "fact" as const,
      ref: "f_ibuprofen",
      label: "Takes ibuprofen (Advil) 400 mg for back pain 2 to 3 times a week.",
      value: null,
      flag: null,
      section: "Patient-reported medicines",
      source_fact: "f_ibuprofen",
      source: { kind: "faculty" as const, ref: null },
      body: null,
    },
    {
      kind: "exam" as const,
      ref: "lung_auscultation",
      label: "Lung auscultation",
      value: "Fine crackles at both lung bases.",
      flag: "abnormal",
      section: "Exam",
      source_fact: null,
      source: { kind: "faculty" as const, ref: null },
      body: null,
    },
  ],
};

type Call = { method: string; url: string; body?: unknown };

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// Records each request the shared client makes and answers with the published fixtures.
function stubStudentApi() {
  const calls: Call[] = [];
  // Cast to fetch: Bun's fetch type has extra methods this stand-in does not need.
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    let body: unknown;
    if (typeof init?.body === "string") body = JSON.parse(init.body);
    calls.push({ method, url, body });
    const path = new URL(url).pathname;
    if (method === "GET" && path === "/api/cases") return jsonResponse(200, [walterCase]);
    if (method === "GET" && path === "/api/cases/walter_greene") return jsonResponse(200, walterCase);
    if (method === "POST" && path === "/api/encounters") return jsonResponse(201, encounter);
    if (method === "GET" && path === "/api/encounters/enc-walter") return jsonResponse(200, encounter);
    return jsonResponse(404, { message: "not found", errors: [], blockers: [] });
  }) as typeof fetch;
  return { calls, client: createApi("http://student.test", fetchImpl) };
}

async function renderApp(client: ReturnType<typeof createApi>) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  let root!: Root;
  await act(async () => {
    root = createRoot(host);
    root.render(<App client={client} />);
  });
  return {
    host,
    async unmount() {
      await act(async () => {
        root.unmount();
      });
      host.remove();
    },
  };
}

function buttonNamed(host: HTMLElement, name: string): HTMLButtonElement | undefined {
  return [...host.querySelectorAll("button")].find((button) => button.textContent?.includes(name));
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

test("a student opens a published case, starts once, and recovers that encounter", async () => {
  window.location.hash = "#s-home";
  const { calls, client } = stubStudentApi();
  const view = await renderApp(client);

  expect(view.host.textContent).toContain("Walter Greene");
  expect(view.host.textContent).toContain("First visit");
  expect(view.host.textContent?.toLowerCase()).not.toContain("due");
  expect(view.host.textContent?.toLowerCase()).not.toContain("cohort");
  expect(calls.some((call) => call.url.includes("/api/studio"))).toBe(false);

  const open = buttonNamed(view.host, "First visit");
  expect(open).toBeTruthy();
  await click(open!);

  expect(window.location.hash).toBe("#s-brief?case=walter_greene&version=1&visit=v1");
  expect(view.host.textContent).toContain("Dietetics student (supervised practice)");
  expect(view.host.textContent).toContain("Take a nutrition-focused history");
  expect(view.host.textContent).toContain("158/92");
  expect(view.host.textContent).toContain("faculty");
  const briefingFetch = calls.find((call) => call.url.includes("/api/cases/walter_greene"));
  expect(briefingFetch?.method).toBe("GET");
  expect(briefingFetch?.url).toContain("visit_id=v1");
  expect(briefingFetch?.url).toContain("version=1");
  expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);

  const start = buttonNamed(view.host, "Start encounter");
  expect(start).toBeTruthy();
  await click(start!);

  expect(window.location.hash).toBe("#s-encounter?case=walter_greene&version=1&visit=v1&encounter=enc-walter");
  const starts = () => calls.filter((call) => call.method === "POST" && call.url.endsWith("/api/encounters")).length;
  const encounterReads = () => calls.filter((call) => call.method === "GET" && call.url.includes("/api/encounters/enc-walter")).length;
  expect(starts()).toBe(1);
  const readsBeforeRefresh = encounterReads();
  expect(readsBeforeRefresh).toBeGreaterThanOrEqual(1);
  expect(view.host.textContent).toContain("Medical nutrition therapy referral.");
  expect(view.host.textContent).toContain("Fine crackles at both lung bases.");
  expect(view.host.textContent).toContain("f_ibuprofen");
  expect(view.host.textContent).toContain("Do you take anything over the counter for pain?");
  expect(view.host.textContent).toContain("Connect microphone");
  expect(calls.some((call) => call.url.endsWith("/api/stt/token"))).toBe(false);
  expect(view.host.querySelector("input, textarea")).toBeNull();
  expect(view.host.textContent).not.toContain("Push to talk");

  await view.unmount();
  window.location.hash = "#s-encounter?case=walter_greene&version=1&visit=v1&encounter=enc-walter";
  const refreshed = await renderApp(client);
  expect(refreshed.host.textContent).toContain("Do you take anything over the counter for pain?");
  expect(refreshed.host.textContent).toContain("Connect microphone");
  expect(refreshed.host.textContent).toContain("f_ibuprofen");
  expect(starts()).toBe(1);
  expect(encounterReads()).toBeGreaterThan(readsBeforeRefresh);
  await refreshed.unmount();
});
