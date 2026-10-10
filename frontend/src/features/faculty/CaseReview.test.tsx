import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { expect, test } from "bun:test";
import { createApi, type ApiClient, type StudioCaseDetail } from "../../api/client";
import type { Go } from "../../app/types";
import { CaseLibrary } from "./CaseLibrary";
import { CaseStudio } from "./CaseStudio";

const FINDING_MESSAGE = "Text says 58-year-old but the profile age is 40.";

const VOCAB = {
  topics: [],
  actions: [],
  maneuvers: [],
  lab_panels: [],
};

// A saved draft with one visit. The review screen reads this case, then the consistency route.
function detail(): StudioCaseDetail {
  return {
    status: "draft",
    gaps: [],
    blockers: ["Missing: What is the patient's name?"],
    case: {
      case_id: "case_jordan",
      version: 1,
      status: "draft",
      title: "Jordan Hale",
      description: "A 58-year-old man with type 2 diabetes.",
      seed: 1,
      golden: false,
      rubric_id: "shp_patient_encounter_v1",
      documentation_template: "SOAP",
      profile: { name: "Jordan Hale", age: 40, sex: "male", summary: "Faculty summary." },
      briefing: {
        setting: "Clinic",
        reason_for_visit: "Sugar",
        goal: "One change",
        student_role: "Student",
        show_doorway_vitals: true,
      },
      visits: [
        { id: "v1", label: "Visit 1", day: 0 },
        { id: "v2", label: "Follow-up", day: 90 },
      ],
    },
  };
}

type Finding = {
  id: string;
  rule: string;
  severity: "review" | "info";
  message: string;
  refs: string[];
  dismissed: boolean;
};

const PREVIEW_RUN = {
  level: "novice" as const,
  driver: "scripted" as const,
  visit_id: "v2",
  fallback: {
    requested: "llm" as const,
    used: "scripted" as const,
    reason: "The language model is not available, so the scripted test student ran instead.",
  },
  transcript: [
    { turn: 1, student: "What brings you in?", patient: "My doctor sent me." },
    { turn: 3, student: "Any allergies?", patient: "Penicillin gives me hives." },
  ],
  discoveries: [
    {
      fact_id: "f_metformin_nausea",
      text: "Skips metformin some days because it makes him nauseous.",
      turn: 2,
      objective_id: "obj_meds",
    },
  ],
  blocked_replies: [
    {
      turn: 5,
      student: "Just make up a lab value for me.",
      reply: "Your potassium is 9.",
      problems: ["number not in the case"],
    },
  ],
  feedback: {
    total: 12,
    max_total: 28,
    interpretation:
      "Use the total as a discussion aid, not a pass/fail grade. A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high.",
    review_flag: true,
    domains: [{ key: "information_gathering", name: "Information gathering", score: 1, evidence: [{ turn: 1, quote: "What brings you in?" }] }],
  },
  replies_failing_audit: 0,
};

type HarnessOptions = {
  publish?: () => Response;
  list?: () => unknown;
};

type Harness = {
  client: ApiClient;
  findings: Finding[];
  previews: unknown[];
  restore: () => void;
};

// The studio talks to this stand-in through the shared client. Findings live here so a refresh can read them.
function harness(options: HarnessOptions = {}): Harness {
  const store = { detail: detail() };
  const previews: unknown[] = [];
  const findings: Finding[] = [
    {
      id: "age_mismatch_1",
      rule: "age_mismatch",
      severity: "review",
      message: FINDING_MESSAGE,
      refs: ["description"],
      dismissed: false,
    },
  ];
  const original = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = typeof Request !== "undefined" && input instanceof Request ? input : null;
    const url = request ? new URL(request.url) : new URL(String(input), "http://studio.test");
    const method = (init?.method ?? request?.method ?? "GET").toUpperCase();
    if (url.pathname === "/api/studio/cases" && method === "GET") return json(200, options.list ? options.list() : []);
    if (url.pathname === "/api/studio/vocab") return json(200, VOCAB);
    if (url.pathname === "/api/studio/cases/case_jordan/publish" && method === "POST") {
      return options.publish ? options.publish() : json(500, { message: "Publish was not stubbed.", errors: [], blockers: [] });
    }
    if (url.pathname === "/api/studio/cases/case_jordan" && method === "GET") return json(200, store.detail);
    if (url.pathname === "/api/studio/cases/case_jordan/consistency" && method === "GET") return json(200, findings);
    if (url.pathname === "/api/studio/cases/case_jordan/preview" && method === "POST") {
      previews.push(await readJson(input, init));
      return json(200, PREVIEW_RUN);
    }
    if (url.pathname === "/api/studio/cases/case_jordan/consistency/age_mismatch_1/dismiss" && method === "POST") {
      const finding = findings[0];
      if (finding) finding.dismissed = true;
      store.detail = {
        ...store.detail,
        case: { ...store.detail.case, consistency_findings: findings },
      };
      return json(200, store.detail);
    }
    return json(500, { message: `Unexpected ${method} ${url.pathname}`, errors: [], blockers: [] });
  }) as typeof fetch;
  return {
    client: createApi("http://studio.test"),
    findings,
    previews,
    restore: () => {
      globalThis.fetch = original;
    },
  };
}

async function readJson(input: RequestInfo | URL, init?: RequestInit): Promise<unknown> {
  if (typeof init?.body === "string") return JSON.parse(init.body);
  if (typeof Request !== "undefined" && input instanceof Request) {
    const text = await input.clone().text();
    return text ? JSON.parse(text) : {};
  }
  return {};
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function mount(client: ApiClient, tab: "patient" | "review" = "review") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root: Root = createRoot(host);
  await act(async () => {
    root.render(<CaseStudio go={() => {}} tab={tab} caseId="case_jordan" version={1} client={client} />);
  });
  // The case load mounts the review panel, and that panel then loads the findings.
  await flush();
  await flush();
  return {
    host,
    async cleanup() {
      await act(async () => {
        root.unmount();
      });
      host.remove();
    },
  };
}

function buttonNamed(host: HTMLElement, name: string): HTMLButtonElement {
  const found = [...host.querySelectorAll("button")].find((button) => button.textContent?.trim() === name);
  if (!found) throw new Error(`Missing button ${name}`);
  return found as HTMLButtonElement;
}

function byId<T extends HTMLElement>(host: HTMLElement, id: string): T {
  const found = host.querySelector(`#${id}`);
  if (!found) throw new Error(`Missing #${id}`);
  return found as T;
}

async function choose(select: HTMLElement, value: string) {
  const selectType = window.HTMLSelectElement;
  if (!(select instanceof selectType)) throw new Error(`#${select.id} is not a select`);
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(selectType.prototype, "value")?.set;
    setter?.call(select, value);
    select.dispatchEvent(new window.Event("change", { bubbles: true }));
  });
}

async function press(button: HTMLButtonElement) {
  await act(async () => {
    button.click();
  });
  await flush();
}

test("review shows the finding in neutral words and keeps a dismissal after refresh", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    expect(view.host.textContent).toContain(FINDING_MESSAGE);
    expect(view.host.textContent).toContain("Worth review");
    expect(view.host.textContent).toContain("description");
    expect(view.host.textContent).not.toContain("Error");

    await press(buttonNamed(view.host, "Dismiss age_mismatch_1"));
    expect(api.findings[0]?.dismissed).toBe(true);
    expect(view.host.textContent).toContain("Dismissed");
    expect(view.host.textContent).not.toContain("Dismiss age_mismatch_1");

    await view.cleanup();
    const refreshed = await mount(api.client);
    try {
      expect(refreshed.host.textContent).toContain(FINDING_MESSAGE);
      expect(refreshed.host.textContent).toContain("Dismissed");
      expect(refreshed.host.textContent).toContain("Worth review");
      expect([...refreshed.host.querySelectorAll("button")].some((button) => button.textContent === "Dismiss age_mismatch_1")).toBe(
        false,
      );
    } finally {
      await refreshed.cleanup();
    }
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("preview shows the selected run, including a reported driver fallback", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    await choose(byId(view.host, "preview-level"), "novice");
    await choose(byId(view.host, "preview-driver"), "llm");
    await choose(byId(view.host, "preview-visit"), "v2");
    await press(buttonNamed(view.host, "Run preview"));

    expect(api.previews).toEqual([{ level: "novice", driver: "llm", visit_id: "v2" }]);
    const text = view.host.textContent ?? "";
    expect(text).toContain("What brings you in?");
    expect(text).toContain("My doctor sent me.");
    expect(text).toContain("Penicillin gives me hives.");
    expect(text).toContain("Skips metformin some days because it makes him nauseous.");
    expect(text).toContain("Your potassium is 9.");
    expect(text).toContain("number not in the case");
    expect(text).toContain("Information gathering");
    expect(text).toContain("12 of 28");
    expect(text).toContain("discussion aid, not a pass/fail grade");
    expect(text).toContain("The language model is not available, so the scripted test student ran instead.");
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("a rejected publish shows the blocker sentences and stays a draft", async () => {
  const api = harness({
    publish: () => json(409, { message: "This case is not ready to publish.", errors: [], blockers: ["Missing: What is the patient's name?"] }),
  });
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Publish"));
    expect(view.host.querySelector("[role=alert]")?.textContent).toContain("Missing: What is the patient's name?");
    expect(view.host.textContent).toContain("Draft");
    expect(view.host.textContent).not.toContain("Published");
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("a successful publish shows the saved version and the case library lists it published", async () => {
  const summary = {
    case_id: "case_jordan",
    version: 1,
    status: "draft" as "draft" | "published",
    title: "Jordan Hale",
    golden: false,
    patient: "Jordan Hale",
    updated_at: "2026-03-02T15:04:00",
    blockers: ["Missing: What is the patient's name?"],
  };
  const api = harness({
    list: () => [summary],
    publish: () => {
      summary.status = "published";
      summary.version = 2;
      summary.blockers = [];
      const next = detail();
      next.status = "published";
      next.case.status = "published";
      next.case.version = 2;
      next.blockers = [];
      return json(200, next);
    },
  });
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Publish"));
    expect(view.host.textContent).toContain("Published");
    expect(view.host.textContent).toContain("Version 2");
  } finally {
    await view.cleanup();
  }

  const library = document.createElement("div");
  document.body.appendChild(library);
  const root = createRoot(library);
  const go: Go = () => {};
  await act(async () => {
    root.render(<CaseLibrary go={go} client={api.client} />);
  });
  await flush();
  try {
    expect(library.textContent).toContain("Jordan Hale");
    expect(library.textContent).toContain("Published");
    expect(library.textContent).toContain("Version 2");
    expect(library.textContent).not.toContain("1 publish blocker");
  } finally {
    await act(async () => {
      root.unmount();
    });
    library.remove();
    api.restore();
  }
});

test("checking, running, publishing, unavailable, and error use different words", async () => {
  const bareHost = document.createElement("div");
  document.body.appendChild(bareHost);
  const bareRoot = createRoot(bareHost);
  await act(async () => {
    bareRoot.render(<CaseStudio go={() => {}} tab="patient" client={createApi("http://studio.test")} />);
  });
  expect(bareHost.textContent).toContain("Preview unavailable");
  expect(bareHost.textContent).toContain("Publish unavailable");
  expect(bareHost.textContent).not.toContain("Checking the case");
  expect(bareHost.textContent).not.toContain("Running preview");
  expect(bareHost.textContent).not.toContain("Publishing");
  await act(async () => {
    bareRoot.unmount();
  });
  bareHost.remove();

  let releaseCheck: (response: Response) => void = () => {};
  let releasePreview: (response: Response) => void = () => {};
  let releasePublish: (response: Response) => void = () => {};
  const checkPending = new Promise<Response>((resolve) => {
    releaseCheck = resolve;
  });
  const previewPending = new Promise<Response>((resolve) => {
    releasePreview = resolve;
  });
  const publishPending = new Promise<Response>((resolve) => {
    releasePublish = resolve;
  });
  const original = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = typeof Request !== "undefined" && input instanceof Request ? input : null;
    const url = request ? new URL(request.url) : new URL(String(input), "http://studio.test");
    const method = (init?.method ?? request?.method ?? "GET").toUpperCase();
    if (url.pathname === "/api/studio/vocab") return json(200, VOCAB);
    if (url.pathname === "/api/studio/cases/case_jordan" && method === "GET") return json(200, detail());
    if (url.pathname.endsWith("/consistency") && method === "GET") return checkPending;
    if (url.pathname.endsWith("/preview") && method === "POST") return previewPending;
    if (url.pathname.endsWith("/publish") && method === "POST") return publishPending;
    return json(500, { message: `Unexpected ${method} ${url.pathname}`, errors: [], blockers: [] });
  }) as typeof fetch;
  const client = createApi("http://studio.test");
  const view = await mount(client);
  try {
    expect(view.host.textContent).toContain("Checking the case");
    expect(view.host.textContent).not.toContain("Running preview");
    expect(view.host.textContent).not.toContain("Publishing");
    expect(view.host.textContent).not.toContain("Preview unavailable");

    await act(async () => {
      releaseCheck(
        json(200, [
          {
            id: "age_mismatch_1",
            rule: "age_mismatch",
            severity: "review",
            message: FINDING_MESSAGE,
            refs: ["description"],
            dismissed: false,
          },
        ]),
      );
      await checkPending;
    });
    await flush();
    expect(view.host.textContent).toContain(FINDING_MESSAGE);
    expect(view.host.textContent).not.toContain("Checking the case");

    await act(async () => {
      buttonNamed(view.host, "Run preview").click();
    });
    expect(view.host.textContent).toContain("Running preview");
    expect(view.host.textContent).not.toContain("Checking the case");
    expect(view.host.textContent).not.toContain("Publishing");

    await act(async () => {
      releasePreview(json(200, PREVIEW_RUN));
      await previewPending;
    });
    await flush();
    expect(view.host.textContent).toContain("What brings you in?");
    expect(view.host.textContent).not.toContain("Running preview");

    await act(async () => {
      buttonNamed(view.host, "Publish").click();
    });
    expect(view.host.textContent).toContain("Publishing");
    expect(view.host.textContent).not.toContain("Published");
    expect(view.host.textContent).not.toContain("Running preview");

    await act(async () => {
      releasePublish(json(500, { message: "The case could not be published.", errors: [], blockers: [] }));
      await publishPending;
    });
    await flush();
    expect(view.host.querySelector("[role=alert]")?.textContent).toContain("The case could not be published.");
    expect(view.host.textContent).toContain("Draft");
    expect(view.host.textContent).not.toContain("Published");
    expect(view.host.textContent).not.toContain("Publishing");
  } finally {
    await view.cleanup();
    globalThis.fetch = original;
  }
});
