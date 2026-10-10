import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import { createApi, type ApiClient } from "../../api/client";
import { routeForScreen, type Go, type StudentRoute } from "../../app/types";
import { Debrief } from "./Debrief";

const route: StudentRoute = {
  caseId: "walter_greene",
  version: 1,
  visitId: "v1",
  encounterId: "enc_1",
};

const quote = "Do you take anything over the counter for pain?";

function domain(
  id: number,
  key: string,
  name: string,
  score: 1 | 2 | 3 | 4 | "N/A",
  extra: { strength?: string; gap?: string; safety?: string } = {},
) {
  return {
    id,
    key,
    name,
    score,
    evidence: score === "N/A" ? [] : [{ turn: 1, quote }],
    strength_demonstrated: extra.strength ?? "",
    important_gap_or_missed_opportunity: extra.gap ?? "",
    safety_or_accuracy_concern: extra.safety ?? "",
    method: "rule-based" as const,
    rule_based_score: score,
  };
}

const feedback = {
  generated_at: "2026-10-10T15:20:00Z",
  fallback_used: false,
  communication_notes: [
    "You asked about suicidal thoughts, which is always the right thing to do. Next time, ask at least one open question first.",
  ],
  documentation: {
    method: "rule-based" as const,
    unsupported: [
      {
        statement: "problem: Blood pressure was 999 over 999.",
        reason: "contains a number that did not come up in the encounter",
      },
    ],
    missing: [{ id: "f_ibuprofen", text: "Takes ibuprofen (Advil) 400 mg for back pain." }],
    supported: [],
  },
  decision_path: {
    visit_id: "v1",
    taken: { id: "b_continued", label: "Continued", summary: "" },
    ghosts: [],
    needs_faculty_review: [],
  },
  elicited: [
    {
      objective_id: "obj_pain",
      objective: "Find the unsafe pain medicine",
      found: [{ fact_id: "f_ibuprofen", text: "Takes ibuprofen", turn: 1 }],
      missed: [{ fact_id: "f_money", text: "Worries about grocery money", suggestion: "Ask about money for food." }],
      actions: [],
    },
  ],
  metrics: {
    turns: 1,
    open_questions: 0,
    closed_questions: 1,
    percent_open: 0,
    reflections: 0,
    validations: 0,
    reflection_to_question_ratio: 0,
    unexplained_jargon: [],
    interruptions: 0,
    student_talk_share: 40,
  },
  rubric: {
    rubric_title: "Patient Encounter Performance Rubric",
    total: 10,
    max_total: 28,
    review_flag: true,
    review_reasons: ["Professionalism, safety, and closure"],
    interpretation:
      "Use the total as a discussion aid, not a pass/fail grade. A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high.",
    strengths: [{ text: "Asked about pain medicine", turn: 1, quote }],
    improvements: [{ text: "Close with a plan", turn: 1, quote }],
    next_attempt: ["Summarize the plan out loud."],
    domains: [
      domain(1, "opening_and_purpose", "Opening and purpose", 2, { strength: "Asked a clear question.", gap: "Introduce yourself." }),
      domain(2, "rapport_respect_empathy", "Rapport, respect, and empathy", 2),
      domain(3, "information_gathering", "Information gathering", 2),
      domain(4, "listening_and_response_to_cues", "Listening and response to cues", 3),
      domain(5, "explanation_and_shared_decisions", "Explanation and shared decisions", 2),
      domain(6, "clinical_reasoning_and_synthesis", "Clinical reasoning and synthesis", "N/A"),
      domain(7, "professionalism_safety_closure", "Professionalism, safety, and closure", 1, {
        safety: "The unsafe pain medicine was not explained.",
      }),
    ],
  },
  safety: [
    {
      fact_id: "f_ibuprofen",
      text: "Takes ibuprofen",
      discovered: true,
      addressed: false,
      patient_words: "Advil for my back.",
    },
  ],
  transcript: [{ turn: 1, student: quote, patient: "Advil for my back.", mode: "template" as const }],
  trust_timeline: [
    { turn: 0, trust: 0, events: [] },
    {
      turn: 1,
      trust: 1,
      events: [{ event: "followed_personal_cue", delta: 1, span: quote, turn: 1, note: null }],
    },
  ],
};

const encounter = {
  encounter_id: "enc_1",
  status: "complete" as const,
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
  transcript: [],
  started_at: "2026-10-10T15:00:00Z",
  ended_at: "2026-10-10T15:20:00Z",
  last_turn: 1,
  documentation_template: {
    id: "PES" as const,
    label: "PES statement (Problem, Etiology, Signs and symptoms)",
    fields: [{ id: "problem", label: "Problem", hint: "The nutrition diagnosis" }],
  },
  saved_documentation: { problem: "Excess sodium at dinner club." },
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

type Call = { url: string; method: string };

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function installFetch(handler: (url: string, method: string) => Response) {
  const calls: Call[] = [];
  const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    const method = init?.method ?? (input instanceof Request ? input.method : "GET");
    calls.push({ url, method });
    return handler(url, method);
  };
  return { calls, client: createApi("http://debrief.test", fetchImpl as typeof fetch) };
}

async function renderDebrief(client: ApiClient, go: Go = () => undefined, current: StudentRoute = route) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<Debrief route={current} client={client} go={go} />);
  });
  return container;
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

test("the debrief shows the rubric, evidence, trust, and the note check", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, encounter);
    if (method === "GET" && url.endsWith("/feedback")) return jsonResponse(200, feedback);
    return jsonResponse(404, { message: "not found", errors: [], blockers: [] });
  });
  const container = await renderDebrief(seen.client);
  await settle();

  expect(seen.calls.some((call) => call.method === "POST")).toBe(false);
  expect(container.textContent).toContain("Walter Greene, 72");
  expect(container.textContent).toContain("Opening and purpose");
  expect(container.textContent).toContain("Clinical reasoning and synthesis");
  expect(container.textContent).toContain("Professionalism, safety, and closure");
  expect(container.textContent).toContain("N/A");
  expect(container.textContent).toContain("1 / 4");
  expect(container.textContent).toContain("10");
  expect(container.textContent).toContain("28");
  expect(container.textContent).toContain("discussion aid");
  expect(container.textContent).toContain("not a pass/fail grade");
  expect(container.textContent).toContain("Needs review");
  expect(container.textContent).toContain("Professionalism, safety, and closure");
  expect(container.textContent).toContain(`Turn 1: ${quote}`);
  expect(container.textContent).toContain("Asked a clear question.");
  expect(container.textContent).toContain("Asked about pain medicine");
  expect(container.textContent).toContain("Introduce yourself.");
  expect(container.textContent).toContain("Close with a plan");
  expect(container.textContent).toContain("The unsafe pain medicine was not explained.");
  expect(container.textContent).toContain("Summarize the plan out loud.");
  expect(container.textContent).toContain("Fact f_ibuprofen");
  expect(container.textContent).toContain("Fact f_money");
  expect(container.textContent).toContain("Found");
  expect(container.textContent).toContain("Missed");
  expect(container.textContent).toContain("Not addressed");
  expect(container.textContent).toContain("Closed questions: 1");
  expect(container.textContent).toContain("Interruptions: 0");
  expect(container.textContent).toContain("Open question share: 0%");
  expect(container.textContent).toContain("always the right thing to do");
  expect(container.textContent).toContain("999");
  expect(container.textContent).toContain("contains a number that did not come up in the encounter");
  expect(container.textContent).toContain("Turn 1: trust 1");
  expect(container.textContent).toContain(`“${quote}”`);
  expect(container.textContent).toContain("Excess sodium at dinner club.");
  expect(container.textContent).not.toContain("Eats breakfast daily");
  expect(container.textContent).not.toContain("Ask Walter to say the plan back");
});

test("a failed feedback read stays visible and keeps the saved note", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, encounter);
    if (method === "GET" && url.endsWith("/feedback")) {
      return jsonResponse(503, { message: "Feedback could not be loaded.", errors: [], blockers: [] });
    }
    return jsonResponse(404, { message: "not found", errors: [], blockers: [] });
  });
  const container = await renderDebrief(seen.client);
  await settle();
  expect(container.textContent).toContain("Feedback could not be loaded.");
  expect(container.textContent).toContain("Excess sodium at dinner club.");
  expect(container.textContent).not.toContain("Opening and purpose");
  expect(container.textContent).not.toContain("Eats breakfast daily");
  expect(container.textContent).not.toContain("1 / 4");
  expect(seen.calls.some((call) => call.method === "POST")).toBe(false);
});

test("the debrief shows the taken path, the other authored outcomes, and whether a next visit exists", async () => {
  const quote = "Do you take anything over the counter for pain?";
  const withPaths = {
    ...feedback,
    decision_path: {
      visit_id: "v1",
      needs_faculty_review: ["Found the ibuprofen use and explained the risk"],
      decisions: [
        {
          id: "dp_nsaid",
          label: "Found the ibuprofen use and explained the risk",
          result: "unclear" as const,
          feedback: "You found that Walter takes ibuprofen and explained why it is risky with heart failure and kidney disease.",
          evidence: [{ turn: 1, quote }],
        },
      ],
      taken: {
        id: "b_improved",
        label: "Stopped ibuprofen and changed dinner-club orders",
        summary:
          "He switched to Tylenol for his back and orders the plain version at the dinner club. Blood pressure and swelling are better.",
        evidence: [{ turn: 1, quote }],
      },
      ghosts: [
        {
          id: "b_partial",
          label: "Stopped ibuprofen but same restaurant food",
          summary: "He stopped the ibuprofen, but dinner-club meals are the same. Swelling is about the same.",
          evidence: [],
        },
        {
          id: "b_nsaid_missed",
          label: "Ibuprofen missed: hospitalized",
          summary:
            "Nobody caught the ibuprofen. Two weeks later he was hospitalized with fluid in his lungs and worse kidney function.",
          evidence: [],
        },
      ],
    },
  };
  const seen = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) return jsonResponse(200, encounter);
    if (method === "GET" && url.endsWith("/feedback")) return jsonResponse(200, withPaths);
    return jsonResponse(404, { message: "not found", errors: [], blockers: [] });
  });
  const visits: string[] = [];
  const container = await renderDebrief(seen.client, (screen) => {
    visits.push(screen);
  });
  await settle();

  expect(container.textContent).toContain("Stopped ibuprofen and changed dinner-club orders");
  expect(container.textContent).toContain("Blood pressure and swelling are better.");
  expect(container.textContent).toContain("Stopped ibuprofen but same restaurant food");
  expect(container.textContent).toContain("Swelling is about the same.");
  expect(container.textContent).toContain("Ibuprofen missed: hospitalized");
  expect(container.textContent).toContain("worse kidney function.");
  expect(container.textContent).toContain("Found the ibuprofen use and explained the risk");
  expect(container.textContent).toContain(`Turn 1: ${quote}`);
  expect(container.textContent).toContain("Unclear");
  expect(container.textContent?.toLowerCase()).not.toContain("probability");
  expect(container.textContent).not.toContain("I switched to Tylenol like you said");
  expect(seen.calls.some((call) => call.url.includes("/api/studio"))).toBe(false);

  const next = buttonNamed(container, "Continue to the next visit");
  expect(next).toBeTruthy();
  await click(next!);
  expect(visits).toEqual(["s-between"]);

  const closed = installFetch((url, method) => {
    if (method === "GET" && url.endsWith("/api/encounters/enc_1")) {
      return jsonResponse(200, { ...encounter, has_next_visit: false, visit_id: "v2", visit_label: "Follow-up" });
    }
    if (method === "GET" && url.endsWith("/feedback")) return jsonResponse(200, withPaths);
    return jsonResponse(404, { message: "not found", errors: [], blockers: [] });
  });
  const lastVisit = await renderDebrief(closed.client);
  await settle();
  expect(lastVisit.textContent).toContain("No further visit is available.");
  expect(buttonNamed(lastVisit, "Continue to the next visit")).toBeUndefined();
});

test("the debrief keeps the encounter id and does not open one when the id is missing", async () => {
  expect(routeForScreen("s-debrief", route).encounterId).toBe("enc_1");
  expect(routeForScreen("s-brief", route).encounterId).toBeNull();

  const seen = installFetch(() => jsonResponse(500, { message: "unused", errors: [], blockers: [] }));
  const container = await renderDebrief(seen.client, () => undefined, {
    caseId: "walter_greene",
    version: 1,
    visitId: "v1",
    encounterId: null,
  });
  expect(container.textContent).toContain("This visit has not been started.");
  expect(seen.calls).toEqual([]);
});
