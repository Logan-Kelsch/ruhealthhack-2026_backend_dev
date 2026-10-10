import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import { createApi, type ApiClient } from "../../api/client";
import { parseHash, routeForScreen, type Go } from "../../app/types";
import { FacultyReview } from "./FacultyReview";

const quote = "Do you take anything over the counter for pain?";

const feedback = {
  generated_at: "2026-10-10T15:20:00Z",
  fallback_used: false,
  communication_notes: [],
  documentation: null,
  decision_path: { visit_id: "v1", taken: null, ghosts: [], needs_faculty_review: [] },
  elicited: [],
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
    student_talk_share: null,
  },
  overrides: null,
  rubric: {
    rubric_title: "Patient Encounter Performance Rubric",
    total: 10,
    max_total: 28,
    review_flag: true,
    review_reasons: ["Professionalism, safety, and closure"],
    interpretation:
      "Use the total as a discussion aid, not a pass/fail grade. A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high.",
    strengths: [],
    improvements: [],
    next_attempt: [],
    domains: [
      {
        id: 7,
        key: "professionalism_safety_closure",
        name: "Professionalism, safety, and closure",
        score: 1,
        evidence: [{ turn: 1, quote }],
        strength_demonstrated: "",
        important_gap_or_missed_opportunity: "Close with a plan.",
        safety_or_accuracy_concern: "The unsafe pain medicine was not explained.",
        method: "rule-based",
        rule_based_score: 1,
      },
    ],
  },
  safety: [],
  transcript: [{ turn: 1, student: quote, patient: "Advil for my back.", mode: "template" }],
  trust_timeline: [],
};

const encounter = {
  encounter_id: "enc_sam",
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
    label: "PES",
    fields: [],
  },
  saved_documentation: null,
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

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function setControl(element: HTMLSelectElement | HTMLTextAreaElement, value: string) {
  const prototype = element.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLSelectElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  setter?.call(element, value);
  element.dispatchEvent(new Event("change", { bubbles: true }));
  element.dispatchEvent(new Event("input", { bubbles: true }));
}

type SavedOverride = {
  scores: { domain: string; score: number | string }[];
  comments: { domain: string; field: string; text: string }[];
  updated_at: string;
};

function reviewClient(options: { failSave?: boolean; missing?: boolean } = {}) {
  let saved: unknown = null;
  const calls: { url: string; method: string }[] = [];
  const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    // openapi-fetch puts PATCH on the Request. init.method is empty in that case.
    const method = init?.method ?? (typeof input === "object" && input !== null && "method" in input ? String(input.method) : "GET");
    calls.push({ url, method });
    if (options.missing) {
      return jsonResponse(404, { message: "encounter missing-encounter not found", errors: [], blockers: [] });
    }
    if (method === "GET" && url.endsWith("/api/encounters/enc_sam")) return jsonResponse(200, encounter);
    if (method === "GET" && url.endsWith("/feedback")) return jsonResponse(200, saved ?? feedback);
    if (method === "PATCH" && url.endsWith("/feedback")) {
      if (options.failSave) {
        return jsonResponse(422, { message: "That score is not supported.", errors: [], blockers: [] });
      }
      const rawBody = typeof init?.body === "string"
        ? init.body
        : typeof input === "object" && input !== null && "clone" in input
          ? await input.clone().text()
          : "{}";
      const body = JSON.parse(rawBody || "{}") as {
        scores?: SavedOverride["scores"];
        comments?: SavedOverride["comments"];
      };
      const overrides: SavedOverride = {
        scores: body.scores ?? [],
        comments: body.comments ?? [],
        updated_at: "2026-10-10T16:00:00Z",
      };
      saved = { ...feedback, overrides };
      return jsonResponse(200, saved);
    }
    return jsonResponse(500, { message: "Feedback could not be loaded.", errors: [], blockers: [] });
  };
  return { calls, client: createApi("http://review.test", fetchImpl as typeof fetch) };
}

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function renderReview(client: ApiClient, encounterId: string | null) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  const go: Go = () => {};
  await act(async () => {
    root.render(<FacultyReview go={go} encounterId={encounterId} client={client} />);
  });
  await act(async () => {
    await Promise.resolve();
  });
  return container;
}

test("a faculty review keeps the encounter id in the address", () => {
  const empty = { caseId: null, version: null, visitId: null, encounterId: null };
  expect(routeForScreen("f-review", empty, { encounterId: "enc_sam" }).encounterId).toBe("enc_sam");
  expect(parseHash("#f-review?encounter=enc_sam").screen).toBe("f-review");
  expect(parseHash("#f-review?encounter=enc_sam").route.encounterId).toBe("enc_sam");
});

test("opening an encounter shows the generated score and its quote", async () => {
  const seen = reviewClient();
  const container = await renderReview(seen.client, "enc_sam");
  const text = container.textContent ?? "";
  expect(text).toContain("Walter Greene");
  expect(text).toContain("Professionalism, safety, and closure");
  expect(text).toContain("1 / 4");
  expect(text).toContain(`Turn 1: ${quote}`);
  expect(text).toContain("The unsafe pain medicine was not explained.");
  expect(text).toContain("discussion aid");
  expect(text).toContain("not a pass/fail grade");
  expect(text).toContain("Needs review");
  expect(text).not.toContain("Faculty score");
  expect(seen.calls.some((call) => call.method === "PATCH")).toBe(false);
});

test("a saved override stays beside the generated score after refresh", async () => {
  const seen = reviewClient();
  const container = await renderReview(seen.client, "enc_sam");
  const score = container.querySelector("select[name=score]") as HTMLSelectElement;
  const comment = container.querySelector("textarea[name=comment]") as HTMLTextAreaElement;
  await act(async () => {
    setControl(score, "3");
    setControl(comment, "Ask about the unsafe pain medicine before ending.");
  });
  const save = [...container.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Save override");
  const scoreValue = (container.querySelector("select[name=score]") as HTMLSelectElement | null)?.value;
  expect({ found: Boolean(save), scoreValue, commentValue: (container.querySelector("textarea[name=comment]") as HTMLTextAreaElement | null)?.value }).toEqual({
    found: true,
    scoreValue: "3",
    commentValue: "Ask about the unsafe pain medicine before ending.",
  });
  await act(async () => {
    save?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await settle();
  expect(container.textContent).toContain("Faculty score");
  expect(container.textContent).toContain("3 / 4");
  expect(container.textContent).toContain("1 / 4");
  expect(container.textContent).toContain("Ask about the unsafe pain medicine before ending.");
  expect(container.textContent).toContain("The unsafe pain medicine was not explained.");
  expect(container.textContent).toContain(`Turn 1: ${quote}`);

  const again = await renderReview(seen.client, "enc_sam");
  expect(again.textContent).toContain("Faculty score");
  expect(again.textContent).toContain("3 / 4");
  expect(again.textContent).toContain("1 / 4");
  expect(again.textContent).toContain("Ask about the unsafe pain medicine before ending.");
  expect(again.textContent).toContain("The unsafe pain medicine was not explained.");
});

test("a failed override does not look saved", async () => {
  const seen = reviewClient({ failSave: true });
  const container = await renderReview(seen.client, "enc_sam");
  const score = container.querySelector("select[name=score]") as HTMLSelectElement;
  await act(async () => {
    setControl(score, "4");
  });
  const save = [...container.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Save override");
  await act(async () => {
    save?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await settle();
  expect(container.textContent).toContain("That score is not supported.");
  expect(container.textContent).toContain("1 / 4");
  expect(container.textContent).not.toContain("Faculty score");
  expect(container.textContent).not.toContain("4 / 4");
});

test("loading, missing, and error states stay distinct", async () => {
  const empty = document.createElement("div");
  document.body.appendChild(empty);
  const root = createRoot(empty);
  mounts.push(root);
  await act(async () => {
    root.render(<FacultyReview go={() => {}} encounterId={null} client={createApi("http://review.test", (async (_input: RequestInfo | URL) => jsonResponse(500, {})) as typeof fetch)} />);
  });
  expect(empty.textContent).toContain("Choose a saved encounter to review.");
  expect(empty.textContent).not.toContain("Loading feedback");
  expect(empty.textContent).not.toContain("Faculty score");

  const waiters: Array<(response: Response) => void> = [];
  const loading = document.createElement("div");
  document.body.appendChild(loading);
  const loadingRoot = createRoot(loading);
  mounts.push(loadingRoot);
  await act(async () => {
    loadingRoot.render(
      <FacultyReview
        go={() => {}}
        encounterId="enc_sam"
        client={createApi(
          "http://review.test",
          (async (_input: RequestInfo | URL) => new Promise<Response>((resolve) => waiters.push(resolve))) as typeof fetch,
        )}
      />,
    );
  });
  expect(loading.textContent).toContain("Loading feedback");
  expect(loading.textContent).not.toContain("Choose a saved encounter to review.");

  await act(async () => {
    for (const resolve of waiters) {
      resolve(jsonResponse(404, { message: "encounter missing-encounter not found", errors: [], blockers: [] }));
    }
    await Promise.resolve();
  });
  expect(loading.textContent).toContain("encounter missing-encounter not found");
  expect(loading.textContent).not.toContain("Loading feedback");
  expect(loading.textContent).not.toContain("Faculty score");

  const broken = await renderReview(
    createApi(
      "http://review.test",
      (async (_input: RequestInfo | URL) => jsonResponse(503, { message: "Feedback could not be loaded.", errors: [], blockers: [] })) as typeof fetch,
    ),
    "enc_sam",
  );
  expect(broken.textContent).toContain("Feedback could not be loaded.");
  expect(broken.textContent).not.toContain("encounter missing-encounter not found");
  expect(broken.textContent).not.toContain("Choose a saved encounter to review.");
  expect(broken.textContent).not.toContain("1 / 4");
});
