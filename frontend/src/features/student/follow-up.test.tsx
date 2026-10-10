import { expect, test } from "bun:test";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createApi } from "../../api/client";
import { App } from "../../app/App";

const DISCHARGE_NOTE =
  "Admitted 4 days for acute on chronic heart failure with fluid overload and acute kidney injury. Home medicines reviewed. Ibuprofen use noted.";
const SAY_LINE = "I switched to Tylenol like you said";
const MISSED_SUMMARY =
  "Nobody caught the ibuprofen. Two weeks later he was hospitalized with fluid in his lungs and worse kidney function.";

const patient = {
  name: "Walter Greene",
  age: 72,
  sex: "male" as const,
  pronouns: "he/him",
  portrait: "walter_greene.jpg",
  speaker: null,
};

const firstBriefing = {
  setting: "Outpatient nutrition clinic",
  reason_for_visit: "Referral for medical nutrition therapy",
  goal: "Take a nutrition-focused history",
  student_role: "Dietetics student (supervised practice)",
  show_doorway_vitals: true,
};

const walterCase = {
  case_id: "walter_greene",
  version: 1,
  title: "Walter Greene: diabetes, heart failure and a dinner club",
  golden: true,
  patient,
  briefing: firstBriefing,
  visits: [
    { id: "v1", label: "First visit", day: 0 },
    { id: "v2", label: "Follow-up, 3 months later", day: 90 },
  ],
  doorway_vitals: [
    { key: "bp", label: "Blood pressure", value: "158/92", unit: "mmHg", source: { kind: "faculty" as const, ref: null } },
  ],
};

const followUpCase = {
  ...walterCase,
  briefing: {
    ...firstBriefing,
    reason_for_visit: "Three-month nutrition follow-up",
    goal: "Review what changed since the first visit and adjust the plan.",
  },
};

const completed = {
  encounter_id: "enc-1",
  status: "complete" as const,
  case_id: "walter_greene",
  case_version: 1,
  visit_id: "v1",
  visit_label: "First visit",
  has_next_visit: true,
  previous_encounter_id: null,
  patient,
  briefing: firstBriefing,
  chart: [],
  transcript: [],
  started_at: "2026-10-10T14:00:00Z",
  ended_at: "2026-10-10T14:20:00Z",
  last_turn: 1,
  documentation_template: {
    id: "PES" as const,
    label: "PES",
    fields: [{ id: "problem", label: "Problem", hint: "The nutrition diagnosis" }],
  },
  saved_documentation: null,
};

const followUp = {
  ...completed,
  encounter_id: "enc-v2",
  status: "active" as const,
  visit_id: "v2",
  visit_label: "Follow-up, 3 months later",
  has_next_visit: false,
  previous_encounter_id: "enc-1",
  ended_at: null,
  last_turn: null,
  briefing: followUpCase.briefing,
  chart: [
    {
      kind: "vital" as const,
      ref: "bp",
      label: "Blood pressure",
      value: "162/94 mmHg",
      flag: null,
      section: "Vitals",
      source_fact: null,
      source: { kind: "faculty" as const, ref: null },
      body: null,
    },
    {
      kind: "artifact" as const,
      ref: "discharge",
      label: "Hospital discharge summary",
      value: null,
      flag: null,
      section: "Documents",
      source_fact: null,
      source: { kind: "faculty" as const, ref: null },
      body: DISCHARGE_NOTE,
    },
  ],
};

const feedback = {
  decision_path: {
    visit_id: "v1",
    needs_faculty_review: [],
    decisions: [
      {
        id: "dp_nsaid",
        label: "Found the ibuprofen use and explained the risk",
        result: "no",
        feedback: "Walter takes ibuprofen for back pain.",
        evidence: [],
      },
    ],
    taken: {
      id: "b_nsaid_missed",
      label: "Ibuprofen missed: hospitalized",
      summary: MISSED_SUMMARY,
      evidence: [],
    },
    ghosts: [
      {
        id: "b_improved",
        label: "Stopped ibuprofen and changed dinner-club orders",
        summary: "He switched to Tylenol for his back and orders the plain version at the dinner club. Blood pressure and swelling are better.",
        evidence: [],
      },
    ],
  },
};

type Call = { method: string; url: string; body?: unknown };

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// Records each request. The follow-up start can be told to fail without inventing a visit.
function stubFollowUp(startStatus: number) {
  const calls: Call[] = [];
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    let body: unknown;
    if (typeof init?.body === "string") body = JSON.parse(init.body);
    else if (input instanceof Request) body = await input.clone().json().catch(() => undefined);
    calls.push({ method, url, body });
    const path = new URL(url).pathname;
    const visitId = new URL(url).searchParams.get("visit_id");
    if (method === "GET" && path === "/api/cases") return jsonResponse(200, [walterCase]);
    if (method === "GET" && path === "/api/cases/walter_greene") {
      return jsonResponse(200, visitId === "v2" ? followUpCase : walterCase);
    }
    if (method === "GET" && path === "/api/encounters/enc-1") return jsonResponse(200, completed);
    if (method === "GET" && path === "/api/encounters/enc-1/feedback") return jsonResponse(200, feedback);
    if (method === "GET" && path === "/api/encounters/enc-v2") return jsonResponse(200, followUp);
    if (method === "POST" && path === "/api/encounters") {
      if (startStatus !== 201) {
        return jsonResponse(startStatus, { message: "this case has no further visits", errors: [], blockers: [] });
      }
      return jsonResponse(201, followUp);
    }
    return jsonResponse(404, { message: "not found", errors: [], blockers: [] });
  }) as typeof fetch;
  return { calls, client: createApi("http://follow-up.test", fetchImpl) };
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

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function posts(calls: Call[]): Call[] {
  return calls.filter((call) => call.method === "POST" && new URL(call.url).pathname === "/api/encounters");
}

test("a finished visit continues into the same follow-up, and a refresh keeps it", async () => {
  window.location.hash = "#s-between?case=walter_greene&version=1&visit=v1&encounter=enc-1";
  const { calls, client } = stubFollowUp(201);
  const view = await renderApp(client);
  await settle();

  expect(view.host.textContent).toContain("Ibuprofen missed: hospitalized");
  expect(view.host.textContent).toContain(MISSED_SUMMARY);
  expect(view.host.textContent).not.toContain(SAY_LINE);
  expect(view.host.textContent).not.toContain("142/86");
  expect(view.host.textContent).not.toContain(DISCHARGE_NOTE);
  expect(view.host.textContent?.toLowerCase()).not.toContain("probability");
  expect(calls.some((call) => call.url.includes("/api/studio"))).toBe(false);
  expect(posts(calls)).toHaveLength(0);

  await view.unmount();
  window.location.hash = "#s-between?case=walter_greene&version=1&visit=v1&encounter=enc-1";
  const refreshedPause = await renderApp(client);
  await settle();
  expect(refreshedPause.host.textContent).toContain(MISSED_SUMMARY);
  expect(posts(calls)).toHaveLength(0);
  await refreshedPause.unmount();

  window.location.hash = "#s-between?case=walter_greene&version=1&visit=v1&encounter=enc-1";
  const again = await renderApp(client);
  await settle();
  const start = buttonNamed(again.host, "Start the next visit");
  expect(start).toBeTruthy();
  await click(start!);
  await settle();

  expect(posts(calls)).toHaveLength(1);
  const body = posts(calls)[0]?.body as { previous_encounter_id?: string; case_id?: string; version?: number };
  expect(body.previous_encounter_id).toBe("enc-1");
  expect(body.case_id).toBe("walter_greene");
  expect(body.version).toBe(1);
  expect(window.location.hash).toBe("#s-brief?case=walter_greene&version=1&visit=v2&encounter=enc-v2");
  expect(again.host.textContent).toContain("Review what changed since the first visit and adjust the plan.");
  expect(again.host.textContent).toContain("162/94");
  expect(again.host.textContent).toContain(DISCHARGE_NOTE);
  expect(again.host.textContent).toContain("faculty");
  expect(again.host.textContent).not.toContain(SAY_LINE);
  expect(again.host.textContent).not.toContain("142/86");
  expect(calls.some((call) => call.url.includes("/api/studio"))).toBe(false);
  expect(calls.filter((call) => call.method === "GET" && call.url.includes("/api/cases/walter_greene"))).toHaveLength(0);

  const enter = buttonNamed(again.host, "Continue this visit");
  expect(enter).toBeTruthy();
  await click(enter!);
  expect(window.location.hash).toBe("#s-encounter?case=walter_greene&version=1&visit=v2&encounter=enc-v2");
  expect(posts(calls)).toHaveLength(1);
  await again.unmount();

  window.location.hash = "#s-brief?case=walter_greene&version=1&visit=v2&encounter=enc-v2";
  const refreshed = await renderApp(client);
  await settle();
  expect(refreshed.host.textContent).toContain(DISCHARGE_NOTE);
  expect(refreshed.host.textContent).toContain("162/94");
  expect(posts(calls)).toHaveLength(1);
  expect(calls.filter((call) => call.method === "GET" && call.url.includes("/api/encounters/enc-v2")).length).toBeGreaterThan(0);
  await refreshed.unmount();
});

test("a later visit without a previous encounter, and a rejected continuation, stay unavailable", async () => {
  window.location.hash = "#s-home";
  const { calls, client } = stubFollowUp(409);
  const home = await renderApp(client);
  await settle();
  const later = buttonNamed(home.host, "Follow-up, 3 months later");
  expect(later).toBeTruthy();
  await click(later!);
  await settle();
  expect(home.host.textContent).toContain("This visit continues from a completed visit.");
  expect(buttonNamed(home.host, "Start encounter")).toBeUndefined();
  expect(posts(calls)).toHaveLength(0);
  expect(home.host.textContent).not.toContain(SAY_LINE);
  expect(home.host.textContent).not.toContain("142/86");
  await home.unmount();

  window.location.hash = "#s-between?case=walter_greene&version=1&visit=v1&encounter=enc-1";
  const paused = await renderApp(client);
  await settle();
  const start = buttonNamed(paused.host, "Start the next visit");
  expect(start).toBeTruthy();
  await click(start!);
  await settle();
  expect(paused.host.textContent).toContain("this case has no further visits");
  expect(window.location.hash).toBe("#s-between?case=walter_greene&version=1&visit=v1&encounter=enc-1");
  expect(paused.host.textContent).not.toContain(DISCHARGE_NOTE);
  await paused.unmount();
});
