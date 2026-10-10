import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { expect, test } from "bun:test";
import { createApi, type ApiClient, type StudioCaseDetail } from "../../api/client";
import { hrefFor, type Go } from "../../app/types";
import { CaseStudio } from "./CaseStudio";

const VOCAB = {
  topics: [{ id: "chief_complaint", description: "Asks why the patient came in" }],
  actions: [{ id: "summarize", description: "Student summarizes what the patient said back to them" }],
  maneuvers: [
    {
      id: "cardiac_auscultation",
      label: "Heart auscultation",
      normal: "Regular rate and rhythm, normal S1 and S2, no murmurs, rubs or gallops.",
    },
  ],
  lab_panels: ["a1c", "bmp"],
};

const MANIA_LABEL = "Asked about mania in their own words";

// A saved draft with one visit and no decision points, so the editor starts blank.
function detail(): StudioCaseDetail {
  return {
    status: "draft",
    gaps: [],
    blockers: [],
    case: {
      case_id: "case_jordan",
      version: 1,
      status: "draft",
      title: "Jordan Hale: high sugars",
      description: "A 72-year-old man with type 2 diabetes.",
      seed: 7,
      golden: false,
      rubric_id: "shp_patient_encounter_v1",
      documentation_template: "SOAP",
      profile: {
        name: "Jordan Hale",
        age: 72,
        sex: "male",
        summary: "Faculty summary.",
        occupation: "Bus driver",
        personality: {
          summary: "Speaks in short sentences.",
          communication_style: "Direct",
          health_literacy: "low",
          mood: "worried",
          traits: { openness: 0.4 },
          example_lines: ["I just want the sugar to stop jumping around."],
        },
      },
      briefing: {
        setting: "Primary care clinic",
        reason_for_visit: "High sugars",
        goal: "Agree on one food change",
        student_role: "Dietetics student",
        show_doorway_vitals: true,
      },
      facts: [
        {
          id: "f_headache",
          category: "presenting",
          cue: false,
          safety: false,
          text: "He has had a headache for three days.",
          say: "My head has hurt for three days.",
          tier: "reluctant",
          status: "draft",
          source: { kind: "faculty", ref: "faculty interview", by: "Dr Lee" },
        },
      ],
      visits: [{ id: "v1", label: "Visit 1", day: 0 }],
    },
  };
}

// Two yes/no checks and two outcomes. The client should accept this tree and send it.
function coveredDetail(): StudioCaseDetail {
  const saved = detail();
  saved.case.visits = [
    {
      id: "v1",
      label: "First visit",
      day: 0,
      decision_points: [
        {
          id: "dp_1",
          label: "Asked about the headache",
          affects: "patient",
          predicate: { topic: "chief_complaint" },
        },
        {
          id: "dp_2",
          label: "Summarized the story",
          affects: "patient",
          predicate: { action: "summarize" },
        },
      ],
      branches: [
        {
          id: "b_1",
          label: "Headache improving",
          summary: "The headache is better at the next visit.",
          status: "draft",
          when: { dp_1: true },
          changes: {
            add_facts: [
              {
                id: "f_b_1",
                category: "history",
                cue: false,
                safety: false,
                text: "The headache is better.",
                tier: "discoverable",
                status: "draft",
                source: { kind: "faculty", ref: null, by: null },
              },
            ],
          },
        },
        {
          id: "b_2",
          label: "Reason still unclear",
          summary: "The reason for the visit is still unclear.",
          status: "draft",
          when: { dp_1: false },
        },
      ],
    },
  ];
  return saved;
}

type Harness = {
  client: ApiClient;
  puts: unknown[];
  approves: unknown[];
  restore: () => void;
};

// Stand-in HTTP for the decision-tree screen. Approval updates only the group that was named.
function harness(options?: { failSave?: boolean; covered?: boolean }): Harness {
  const store = { detail: options?.covered ? coveredDetail() : detail() };
  const puts: unknown[] = [];
  const approves: unknown[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = typeof Request !== "undefined" && input instanceof Request ? input : null;
    const url = request ? new URL(request.url) : new URL(String(input), "http://studio.test");
    const method = (init?.method ?? request?.method ?? "GET").toUpperCase();
    if (url.pathname === "/api/studio/vocab") return json(200, VOCAB);
    if (url.pathname === "/api/studio/cases/case_jordan" && method === "GET") return json(200, store.detail);
    if (url.pathname === "/api/studio/cases/case_jordan" && method === "PUT") {
      const body = (await readJson(input, init)) as StudioCaseDetail["case"];
      puts.push(body);
      if (options?.failSave) {
        return json(422, { message: "The decision point could not be saved.", errors: [], blockers: [] });
      }
      store.detail = { ...store.detail, case: body, status: body.status };
      return json(200, store.detail);
    }
    if (url.pathname === "/api/studio/cases/case_jordan/approve" && method === "POST") {
      const body = (await readJson(input, init)) as { group: string; keys?: string[]; status: "draft" | "approved" };
      approves.push(body);
      const next = structuredClone(store.detail);
      const keys = new Set<string>(body.keys ?? []);
      stampApproval(next, body.group, keys, body.status);
      store.detail = next;
      return json(200, next);
    }
    return json(500, { message: `Unexpected ${method} ${url.pathname}`, errors: [], blockers: [] });
  }) as typeof fetch;
  return {
    client: createApi("http://studio.test"),
    puts,
    approves,
    restore() {
      globalThis.fetch = original;
    },
  };
}

// Copy the approved status onto the named outcome or visit change, and leave the other group alone.
function stampApproval(
  detail: StudioCaseDetail,
  group: string,
  keys: Set<string>,
  status: "draft" | "approved",
) {
  detail.case.visits = (detail.case.visits ?? []).map((visit) => {
    if (group === "visit_changes" && keys.has(visit.id) && visit.changes) {
      return {
        ...visit,
        changes: {
          ...visit.changes,
          vitals: (visit.changes.vitals ?? []).map((vital) => ({ ...vital, status })),
        },
      };
    }
    if (group !== "branches") return visit;
    return {
      ...visit,
      branches: (visit.branches ?? []).map((branch) => {
        if (!keys.has(branch.id)) return branch;
        const changes = branch.changes;
        return {
          ...branch,
          status,
          changes: changes
            ? {
                ...changes,
                add_facts: (changes.add_facts ?? []).map((fact) => ({ ...fact, status })),
              }
            : changes,
        };
      }),
    };
  });
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function readJson(input: RequestInfo | URL, init?: RequestInit): Promise<unknown> {
  if (typeof Request !== "undefined" && input instanceof Request) return input.json();
  return JSON.parse(String(init?.body ?? "null"));
}

// Let the load request finish and React paint the result.
async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

// Open the decision tree the way a refresh would, and keep the case id in the address bar.
async function mount(client: ApiClient) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root: Root = createRoot(host);
  const go: Go = (screen, opts) => {
    window.history.replaceState(null, "", hrefFor(screen, opts));
  };
  await act(async () => {
    root.render(<CaseStudio go={go} tab="tree" caseId="case_jordan" version={1} client={client} />);
  });
  await flush();
  let removed = false;
  return {
    host,
    async cleanup() {
      if (removed) return;
      removed = true;
      await act(async () => {
        root.unmount();
      });
      host.remove();
    },
  };
}

// The control the faculty member would edit. A missing id fails the test instead of skipping it.
function byId<T extends HTMLElement>(host: HTMLElement, id: string): T {
  const found = host.querySelector(`#${id}`);
  if (!found) throw new Error(`Missing #${id}`);
  return found as T;
}

// Find a button by the words on it, which is how a person chooses it.
function buttonNamed(host: HTMLElement, name: string): HTMLButtonElement {
  const found = [...host.querySelectorAll("button")].find((button) => button.textContent?.trim() === name);
  if (!found) throw new Error(`Missing button ${name}`);
  return found as HTMLButtonElement;
}

// Set the field the way a keystroke does, so React sees the change.
async function typeInto(field: HTMLElement, value: string) {
  const inputType = window.HTMLInputElement;
  const areaType = window.HTMLTextAreaElement;
  if (!(field instanceof inputType) && !(field instanceof areaType)) {
    throw new Error(`#${field.id} is not a text field`);
  }
  await act(async () => {
    const prototype = field instanceof areaType ? areaType.prototype : inputType.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    setter?.call(field, value);
    field.dispatchEvent(new window.Event("input", { bubbles: true }));
    field.dispatchEvent(new window.Event("change", { bubbles: true }));
  });
}

// Choose a listed option. A sentence typed into a box is not one of these values.
async function choose(field: HTMLElement, value: string) {
  const selectType = window.HTMLSelectElement;
  if (!(field instanceof selectType)) throw new Error(`#${field.id} is not a list`);
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(selectType.prototype, "value")?.set;
    setter?.call(field, value);
    field.dispatchEvent(new window.Event("change", { bubbles: true }));
  });
}

// Click and wait for the request that follows.
async function press(button: HTMLButtonElement) {
  await act(async () => {
    button.click();
  });
  await flush();
}

test("authored checks save through the case, survive refresh, and approve one item at a time", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    await typeInto(byId(view.host, "visit-label-v1"), "First visit");
    await typeInto(byId(view.host, "visit-day-v1"), "14");
    await typeInto(byId(view.host, "visit-mood-v1"), "worried");
    await typeInto(byId(view.host, "visit-reason-v1"), "Headache follow-up");
    await typeInto(byId(view.host, "visit-bp-v1"), "128/82");

    await press(buttonNamed(view.host, "Add decision point"));
    await press(buttonNamed(view.host, "Add decision point"));
    await typeInto(byId(view.host, "decision-label-dp_1"), MANIA_LABEL);
    await choose(byId(view.host, "decision-kind-dp_1"), "topic");
    await choose(byId(view.host, "decision-value-dp_1"), "chief_complaint");
    await typeInto(byId(view.host, "decision-label-dp_2"), "Summarized the story");
    await choose(byId(view.host, "decision-kind-dp_2"), "action");
    await choose(byId(view.host, "decision-value-dp_2"), "summarize");

    await press(buttonNamed(view.host, "Add outcome"));
    await press(buttonNamed(view.host, "Add outcome"));
    await typeInto(byId(view.host, "outcome-label-b_1"), "Headache improving");
    await typeInto(byId(view.host, "outcome-summary-b_1"), "The headache is better at the next visit.");
    await choose(byId(view.host, "outcome-when-b_1-dp_1"), "yes");
    await choose(byId(view.host, "outcome-when-b_1-dp_2"), "either");
    await typeInto(byId(view.host, "outcome-fact-b_1"), "The headache is better.");
    await typeInto(byId(view.host, "outcome-label-b_2"), "Reason still unclear");
    await typeInto(byId(view.host, "outcome-summary-b_2"), "The reason for the visit is still unclear.");
    await choose(byId(view.host, "outcome-when-b_2-dp_1"), "no");
    await choose(byId(view.host, "outcome-when-b_2-dp_2"), "either");

    await press(buttonNamed(view.host, "Save case"));
    expect(api.puts).toHaveLength(1);
    const saved = api.puts[0] as StudioCaseDetail["case"];
    const visit = saved.visits?.[0];
    const first = visit?.decision_points?.[0];
    const second = visit?.decision_points?.[1];
    expect(JSON.stringify(first?.predicate)).toBe(JSON.stringify({ topic: "chief_complaint" }));
    expect(JSON.stringify(first?.predicate)).not.toContain("mania");
    expect(first?.label).toBe(MANIA_LABEL);
    expect(second?.predicate).toEqual({ action: "summarize" });
    expect(visit?.id).toBe("v1");
    expect(visit?.label).toBe("First visit");
    expect(visit?.day).toBe(14);
    expect(visit?.changes?.mood).toBe("worried");
    expect(visit?.changes?.briefing?.reason_for_visit).toBe("Headache follow-up");
    expect(visit?.changes?.vitals?.[0]).toMatchObject({ key: "bp", value: "128/82", status: "draft" });
    expect(visit?.branches?.[0]).toMatchObject({
      id: "b_1",
      status: "draft",
      when: { dp_1: true },
    });
    expect(visit?.branches?.[0].changes?.add_facts?.[0]).toMatchObject({
      text: "The headache is better.",
      status: "draft",
    });
    expect(visit?.branches?.[1]).toMatchObject({ id: "b_2", status: "draft", when: { dp_1: false } });
    expect(visit?.branches?.[1].when).not.toHaveProperty("dp_2");
    expect(window.location.search).toContain("case=case_jordan");
    expect(window.location.search).toContain("version=1");
    expect(window.location.hash).toContain("f-studio");
    expect(view.host.textContent).toContain("Saved");

    await view.cleanup();
    const refreshed = await mount(api.client);
    try {
      expect(byId<HTMLInputElement>(refreshed.host, "visit-label-v1").value).toBe("First visit");
      expect(byId<HTMLInputElement>(refreshed.host, "visit-day-v1").value).toBe("14");
      expect(byId<HTMLInputElement>(refreshed.host, "visit-mood-v1").value).toBe("worried");
      expect(byId<HTMLInputElement>(refreshed.host, "visit-reason-v1").value).toBe("Headache follow-up");
      expect(byId<HTMLInputElement>(refreshed.host, "visit-bp-v1").value).toBe("128/82");
      expect(byId<HTMLInputElement>(refreshed.host, "decision-label-dp_1").value).toBe(MANIA_LABEL);
      expect(byId<HTMLSelectElement>(refreshed.host, "decision-value-dp_1").value).toBe("chief_complaint");
      expect(byId<HTMLSelectElement>(refreshed.host, "decision-value-dp_2").value).toBe("summarize");
      expect(refreshed.host.querySelector("#outcome-status-b_1")?.textContent).toBe("Draft");
      expect(refreshed.host.querySelector("#visit-change-status-v1")?.textContent).toBe("Draft");

      await press(buttonNamed(refreshed.host, "Approve b_1"));
      expect(api.approves[0]).toEqual({ group: "branches", keys: ["b_1"], status: "approved" });
      expect(refreshed.host.querySelector("#outcome-status-b_1")?.textContent).toBe("Approved");
      expect(refreshed.host.querySelector("#outcome-status-b_2")?.textContent).toBe("Draft");
      expect(refreshed.host.querySelector("#visit-change-status-v1")?.textContent).toBe("Draft");

      await press(buttonNamed(refreshed.host, "Approve visit v1"));
      expect(api.approves[1]).toEqual({ group: "visit_changes", keys: ["v1"], status: "approved" });
      expect(refreshed.host.querySelector("#visit-change-status-v1")?.textContent).toBe("Approved");
      expect(refreshed.host.querySelector("#outcome-status-b_2")?.textContent).toBe("Draft");
    } finally {
      await refreshed.cleanup();
    }
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("one decision point is not saved and does not look saved", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Add decision point"));
    await typeInto(byId(view.host, "decision-label-dp_1"), "Asked one question");
    await press(buttonNamed(view.host, "Save case"));
    expect(view.host.textContent).toContain("2 to 4");
    expect(api.puts).toHaveLength(0);
    expect(view.host.textContent).not.toContain("Saved");
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("an outcome that skips a yes or no result is not saved", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Add decision point"));
    await press(buttonNamed(view.host, "Add decision point"));
    await typeInto(byId(view.host, "decision-label-dp_1"), "Asked about the headache");
    await typeInto(byId(view.host, "decision-label-dp_2"), "Summarized the story");
    await press(buttonNamed(view.host, "Add outcome"));
    await typeInto(byId(view.host, "outcome-label-b_1"), "Both yes");
    await typeInto(byId(view.host, "outcome-summary-b_1"), "Only the yes and yes path.");
    await choose(byId(view.host, "outcome-when-b_1-dp_1"), "yes");
    await choose(byId(view.host, "outcome-when-b_1-dp_2"), "yes");
    await press(buttonNamed(view.host, "Save case"));
    expect(view.host.textContent).toContain("does not cover");
    expect(api.puts).toHaveLength(0);
    expect(view.host.textContent).not.toContain("Saved");
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("a rejected save stays visible and does not look saved or approved", async () => {
  const api = harness({ failSave: true, covered: true });
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Save case"));
    expect(view.host.querySelector("[role=alert]")?.textContent).toContain("The decision point could not be saved.");
    expect(view.host.textContent).not.toContain("Saved");
    expect(view.host.querySelector("#outcome-status-b_1")?.textContent).toBe("Draft");
    expect(view.host.querySelector("#outcome-status-b_2")?.textContent).toBe("Draft");
  } finally {
    await view.cleanup();
    api.restore();
  }
});
