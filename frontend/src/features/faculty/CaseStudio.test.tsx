import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { expect, test } from "bun:test";
import { createApi, type ApiClient, type StudioCaseDetail } from "../../api/client";
import { CaseStudio } from "./CaseStudio";

const LOOKUP_DISPLAY = "Lookup-only hyperglycemia label";

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

// A saved draft the screen can load. The fact id and source are the values a refresh must keep.
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
          unlock: { topics: ["chief_complaint"], min_trust: 2, requires_facts: [] },
          source: { kind: "faculty", ref: "faculty interview", by: "Dr Lee" },
        },
      ],
      vitals: [
        {
          key: "bp",
          label: "Blood pressure",
          value: "120/80",
          unit: "mmHg",
          status: "draft",
          source: { kind: "faculty", ref: "typed by faculty", by: "Dr Lee" },
        },
      ],
      labs: [
        {
          id: "lab_na",
          key: "na",
          name: "Sodium",
          value: 140,
          unit: "mmol/L",
          status: "draft",
          ref_low: 135,
          ref_high: 145,
          source: { kind: "faculty", ref: "outside lab", by: "Dr Lee" },
        },
      ],
      exam: [
        {
          maneuver: "cardiac_auscultation",
          finding: "Regular rate and rhythm, no murmur.",
          abnormal: false,
          status: "draft",
          source: { kind: "faculty", ref: null, by: "Dr Lee" },
        },
      ],
      diagnoses: [],
      medications: [
        {
          name: "Metformin",
          dose: "500 mg",
          frequency: "twice daily",
          purpose: "Blood sugar",
          status: "draft",
          source: { kind: "faculty", ref: null, by: "Dr Lee" },
        },
      ],
      allergies: [
        {
          substance: "Penicillin",
          reaction: "Rash",
          status: "draft",
          source: { kind: "faculty", ref: null, by: "Dr Lee" },
        },
      ],
      objectives: [
        {
          id: "obj_headache",
          text: "Ask when the headache started.",
          expected_discoveries: ["f_headache"],
          expected_actions: ["summarize"],
          status: "draft",
        },
      ],
      visits: [{ id: "v1", label: "Visit 1", day: 0 }],
    },
  };
}

type Harness = {
  client: ApiClient;
  store: { detail: StudioCaseDetail };
  puts: unknown[];
  approves: unknown[];
  autofills: unknown[];
  paths: string[];
  restore: () => void;
};

// Stand-in HTTP for one studio case. The component uses the shared client against this.
function harness(options?: { failSave?: boolean; failAutofill?: boolean }): Harness {
  const store = { detail: detail() };
  const puts: unknown[] = [];
  const approves: unknown[] = [];
  const autofills: unknown[] = [];
  const paths: string[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    // openapi-fetch passes a Request. String(request) is not the URL.
    const request = typeof Request !== "undefined" && input instanceof Request ? input : null;
    const url = request ? new URL(request.url) : new URL(String(input), "http://studio.test");
    const method = (init?.method ?? request?.method ?? "GET").toUpperCase();
    paths.push(`${method} ${url.pathname}`);
    if (url.pathname === "/api/studio/vocab") return json(200, VOCAB);
    if (url.pathname === "/api/studio/lookup/icd10") {
      const query = url.searchParams.get("q");
      if (query === "sugar") return json(200, [{ code: "E11.65", display: LOOKUP_DISPLAY }]);
      return json(200, []);
    }
    if (url.pathname === "/api/studio/cases/case_jordan" && method === "GET") return json(200, store.detail);
    if (url.pathname === "/api/studio/cases/case_jordan" && method === "PUT") {
      const body = (await readJson(input, init)) as StudioCaseDetail["case"];
      puts.push(body);
      if (options?.failSave) {
        return json(422, { message: "The case could not be saved.", errors: [], blockers: [] });
      }
      store.detail = { ...store.detail, case: body, status: body.status };
      return json(200, store.detail);
    }
    if (url.pathname === "/api/studio/cases/case_jordan/approve" && method === "POST") {
      const body = (await readJson(input, init)) as { group: string; keys?: string[]; status: "draft" | "approved" };
      approves.push(body);
      const next = structuredClone(store.detail);
      const keys = new Set<string>(body.keys ?? []);
      if (body.group === "facts") {
        next.case.facts = (next.case.facts ?? []).map((fact) =>
          keys.has(fact.id) ? { ...fact, status: body.status } : fact,
        );
      }
      store.detail = next;
      return json(200, next);
    }
    if (url.pathname === "/api/studio/cases/case_jordan/autofill" && method === "POST") {
      const body = await readJson(input, init);
      autofills.push(body);
      if (options?.failAutofill) {
        return json(500, { message: "Auto-fill could not be saved.", errors: [], blockers: [] });
      }
      const next = structuredClone(store.detail);
      next.case.labs = [
        ...(next.case.labs ?? []),
        {
          id: "lab_egfr",
          key: "egfr",
          name: "eGFR (CKD-EPI 2021)",
          value: 45,
          unit: "mL/min/1.73m2",
          status: "draft" as const,
          source: { kind: "computed" as const, ref: "CKD-EPI 2021 creatinine equation (race-free)", by: null },
        },
      ];
      store.detail = next;
      return json(200, {
        ...next,
        added: { labs: ["lab_egfr"], vitals: [] },
        notes: ["Used condition rules for: diabetes."],
      });
    }
    return json(500, { message: `Unexpected ${method} ${url.pathname}`, errors: [], blockers: [] });
  }) as typeof fetch;
  return {
    client: createApi("http://studio.test"),
    store,
    puts,
    approves,
    autofills,
    paths,
    restore: () => {
      globalThis.fetch = original;
    },
  };
}

// The body may be on init or already consumed into the Request.
async function readJson(input: RequestInfo | URL, init?: RequestInit): Promise<unknown> {
  if (typeof init?.body === "string") return JSON.parse(init.body);
  if (typeof Request !== "undefined" && input instanceof Request) {
    const text = await input.clone().text();
    return text ? JSON.parse(text) : {};
  }
  return {};
}

// A JSON response with the status the screen should treat as success or failure.
function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// Let the load request finish and React paint the result.
async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

// Render the studio on the saved case, the same way a refresh would open it.
async function mount(client: ApiClient) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root: Root = createRoot(host);
  await act(async () => {
    root.render(<CaseStudio go={() => {}} tab="patient" caseId="case_jordan" version={1} client={client} />);
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

// Click and wait for the request that follows.
async function press(button: HTMLButtonElement) {
  await act(async () => {
    button.click();
  });
  await flush();
}

test("supported edits persist through the shared client and survive refresh", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    expect(view.host.textContent).toContain("Source: faculty · faculty interview");
    await typeInto(byId(view.host, "profile-name"), "Edited Name");
    await typeInto(byId(view.host, "personality-summary"), "Says less when tired.");
    await typeInto(byId(view.host, "briefing-goal"), "Name one food to change.");
    await typeInto(byId(view.host, "fact-text-f_headache"), "He has had a headache for four days.");
    await typeInto(byId(view.host, "vital-value-bp"), "118/76");
    await typeInto(byId(view.host, "lab-value-lab_na"), "141");
    await typeInto(byId(view.host, "exam-finding-cardiac_auscultation"), "A soft murmur is present.");
    await typeInto(byId(view.host, "medication-dose-0"), "1000 mg");
    await typeInto(byId(view.host, "allergy-reaction-0"), "Hives");
    await press(buttonNamed(view.host, "Learning objectives"));
    await typeInto(byId(view.host, "objective-text-obj_headache"), "Ask how the headache started.");
    await press(buttonNamed(view.host, "Save case"));

    expect(api.puts).toHaveLength(1);
    const saved = api.puts[0] as StudioCaseDetail["case"];
    expect(saved.profile.name).toBe("Edited Name");
    expect(saved.profile.personality?.summary).toBe("Says less when tired.");
    expect(saved.briefing?.goal).toBe("Name one food to change.");
    expect(saved.facts?.[0].id).toBe("f_headache");
    expect(saved.facts?.[0].text).toBe("He has had a headache for four days.");
    expect(saved.facts?.[0].tier).toBe("reluctant");
    expect(saved.facts?.[0].unlock?.topics).toEqual(["chief_complaint"]);
    expect(saved.facts?.[0].source).toEqual({ kind: "faculty", ref: "faculty interview", by: "Dr Lee" });
    expect(saved.vitals?.[0].value).toBe("118/76");
    expect(saved.vitals?.[0].source?.kind).toBe("faculty");
    expect(saved.labs?.[0].value).toBe(141);
    expect(saved.labs?.[0].source?.ref).toBe("outside lab");
    expect(saved.exam?.[0].finding).toBe("A soft murmur is present.");
    expect(saved.medications?.[0].dose).toBe("1000 mg");
    expect(saved.allergies?.[0].reaction).toBe("Hives");
    expect(saved.objectives?.[0].text).toBe("Ask how the headache started.");
    expect(saved.objectives?.[0].expected_discoveries).toEqual(["f_headache"]);
    expect(view.host.textContent).toContain("Saved");

    await view.cleanup();
    const refreshed = await mount(api.client);
    try {
      expect(byId<HTMLInputElement>(refreshed.host, "profile-name").value).toBe("Edited Name");
      expect(byId<HTMLTextAreaElement>(refreshed.host, "fact-text-f_headache").value).toBe(
        "He has had a headache for four days.",
      );
      expect(refreshed.host.textContent).toContain("Source: faculty · faculty interview");
    } finally {
      await refreshed.cleanup();
    }
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("refresh shows the approval state that was saved", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    expect(view.host.textContent).toContain("Draft");
    await press(buttonNamed(view.host, "Approve f_headache"));
    expect(api.approves).toEqual([{ group: "facts", keys: ["f_headache"], status: "approved" }]);
    await view.cleanup();
    const refreshed = await mount(api.client);
    try {
      expect(refreshed.host.textContent).toContain("Approved");
      expect(buttonNamed(refreshed.host, "Return f_headache to draft")).toBeTruthy();
      await press(buttonNamed(refreshed.host, "Return f_headache to draft"));
      expect(api.approves[1]).toEqual({ group: "facts", keys: ["f_headache"], status: "draft" });
    } finally {
      await refreshed.cleanup();
    }
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("diagnosis lookup shows the API result and other lookups stay unavailable", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    expect(view.host.textContent).not.toContain(LOOKUP_DISPLAY);
    expect(view.host.textContent).toContain("Medication lookup is not available");
    expect(view.host.textContent).toContain("Allergy lookup is not available");
    await press(buttonNamed(view.host, "Files and sources"));
    expect(view.host.textContent).toContain("This part of the studio is not available yet.");
    await press(buttonNamed(view.host, "Decision tree"));
    expect(view.host.textContent).toContain("This part of the studio is not available yet.");
    await press(buttonNamed(view.host, "Patient"));
    await typeInto(byId(view.host, "diagnosis-query"), "sugar");
    await press(buttonNamed(view.host, "Look up diagnosis"));
    expect(view.host.textContent).toContain(LOOKUP_DISPLAY);
    expect(view.host.textContent).toContain("E11.65");
    await press(buttonNamed(view.host, `Use ${LOOKUP_DISPLAY}`));
    await press(buttonNamed(view.host, "Save case"));
    const saved = api.puts[0] as StudioCaseDetail["case"];
    expect(saved.diagnoses?.[0].name).toBe(LOOKUP_DISPLAY);
    expect(saved.diagnoses?.[0].codes?.[0]).toEqual({
      system: "ICD-10-CM",
      code: "E11.65",
      display: LOOKUP_DISPLAY,
    });
    expect(saved.diagnoses?.[0].status).toBe("draft");
    expect(api.paths.some((path) => path.includes("rxnorm") || path.includes("medication"))).toBe(false);
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("a failed save keeps the unsaved edits and does not look successful", async () => {
  const api = harness({ failSave: true });
  const view = await mount(api.client);
  try {
    await typeInto(byId(view.host, "profile-name"), "Edited Name");
    await typeInto(byId(view.host, "fact-text-f_headache"), "He has had a headache for four days.");
    await press(buttonNamed(view.host, "Save case"));
    expect(api.puts).toHaveLength(1);
    expect(byId<HTMLInputElement>(view.host, "profile-name").value).toBe("Edited Name");
    expect(byId<HTMLTextAreaElement>(view.host, "fact-text-f_headache").value).toBe(
      "He has had a headache for four days.",
    );
    expect(view.host.querySelector("[role=alert]")?.textContent).toContain("The case could not be saved.");
    expect(view.host.textContent).not.toContain("Saved");
    expect(view.host.textContent).toContain("Jordan Hale");
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("removing a referenced fact shows the objective and keeps the fact", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Remove f_headache"));
    expect(view.host.querySelector("[role=alert]")?.textContent).toContain("obj_headache");
    expect(byId<HTMLTextAreaElement>(view.host, "fact-text-f_headache").value).toBe(
      "He has had a headache for three days.",
    );
    expect(api.puts).toHaveLength(0);
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("auto-fill shows the proposed value, source, note, and draft status", async () => {
  const api = harness();
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Propose values"));
    expect(view.host.textContent).toContain("45");
    expect(view.host.textContent).toContain("computed");
    expect(view.host.textContent).toContain("CKD-EPI 2021 creatinine equation (race-free)");
    expect(view.host.textContent).toContain("Used condition rules for: diabetes.");
    expect(view.host.textContent).toContain("Draft");
    expect(api.autofills).toHaveLength(1);
  } finally {
    await view.cleanup();
    api.restore();
  }
});

test("a failed auto-fill stays an error and does not show a proposed value", async () => {
  const api = harness({ failAutofill: true });
  const view = await mount(api.client);
  try {
    await press(buttonNamed(view.host, "Propose values"));
    expect(view.host.querySelector("[role=alert]")?.textContent).toContain("Auto-fill could not be saved.");
    expect(view.host.textContent).not.toContain("Used condition rules for: diabetes.");
    expect(view.host.textContent).not.toContain("CKD-EPI 2021 creatinine equation (race-free)");
    expect(byId<HTMLInputElement>(view.host, "lab-value-lab_na").value).toBe("140");
  } finally {
    await view.cleanup();
    api.restore();
  }
});
