import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import { createApi } from "../../api/client";
import type { Go } from "../../app/types";
import { StudentHome } from "./StudentHome";

const walter = {
  case_id: "walter_greene",
  version: 1,
  golden: true,
  title: "Walter Greene: diabetes, heart failure and a dinner club",
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
  visits: [{ id: "v1", label: "First visit", day: 0 }],
  doorway_vitals: [],
};

const sam = {
  encounter_id: "enc_sam",
  case_id: "walter_greene",
  visit_id: "v1",
  student_name: "Sam",
  status: "complete" as const,
  started_at: "2026-10-10T15:00:00Z",
  rubric_total: 10,
  review_flag: true,
  previous_encounter_id: null,
  patient_name: "Walter Greene",
  case_title: "Walter Greene: diabetes, heart failure and a dinner club",
  visit_label: "First visit",
};

const riley = {
  ...sam,
  encounter_id: "enc_riley",
  student_name: "Riley",
  status: "active" as const,
  review_flag: false,
  rubric_total: null,
  patient_name: "Alina Reyes",
  case_id: "alina_reyes",
  case_title: "Alina Reyes: low mood, and what the questionnaire hides",
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

function handlerFor(casesBody: unknown, encountersBody: unknown, statuses: { cases?: number; encounters?: number } = {}) {
  return async (input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/cases")) {
      return jsonResponse(statuses.cases ?? 200, casesBody);
    }
    if (url.includes("/api/encounters")) {
      return jsonResponse(statuses.encounters ?? 200, encountersBody);
    }
    return jsonResponse(404, { message: "not found", errors: [], blockers: [] });
  };
}

async function renderHome(fetchImpl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>, go: Go = () => {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<StudentHome go={go} client={createApi("http://student.test", fetchImpl as typeof fetch)} />);
  });
  await act(async () => {
    await Promise.resolve();
  });
  return container;
}

test("student history shows saved encounters and opens the debrief", async () => {
  const visits: { screen: string; encounterId?: string | null; caseId?: string; visitId?: string }[] = [];
  const go: Go = (screen, opts) => {
    visits.push({ screen, encounterId: opts?.encounterId, caseId: opts?.caseId, visitId: opts?.visitId });
  };
  const container = await renderHome(
    handlerFor([walter], { encounters: [sam], total: 1, limit: 200 }),
    go,
  );
  const text = container.textContent ?? "";
  expect(text).toContain("Walter Greene");
  expect(text).toContain("First visit");
  expect(text).toContain("Sam");
  expect(text).toContain("Complete");
  expect(text).toContain("Needs review");
  expect(text).toContain("1 saved encounter");
  expect(text).not.toContain("Due ");
  expect(text).not.toContain("assigned");
  expect(text).not.toContain("recommendation");
  expect(text).not.toContain("Class average");

  const open = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Sam"));
  await act(async () => {
    open?.click();
  });
  expect(visits).toEqual([{ screen: "s-debrief", encounterId: "enc_sam", caseId: "walter_greene", visitId: "v1" }]);
});

test("a short history says how many encounters were left out", async () => {
  const container = await renderHome(handlerFor([walter], { encounters: [sam], total: 2, limit: 1 }));
  expect(container.textContent).toContain("Showing 1 of 2");
  expect(container.textContent).toContain("Sam");
  expect(container.textContent).not.toContain("Riley");
  expect(container.textContent).not.toContain("2 saved encounters");
});

test("case and history loading, empty, and error states stay distinct", async () => {
  const waiters: Array<(response: Response) => void> = [];
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(
      <StudentHome
        go={() => {}}
        client={createApi(
          "http://student.test",
          (async (_input: RequestInfo | URL) => new Promise<Response>((resolve) => waiters.push(resolve))) as typeof fetch,
        )}
      />,
    );
  });
  expect(container.textContent).toContain("Loading published cases");
  expect(container.textContent).toContain("Loading your encounters");
  expect(container.textContent).not.toContain("No published cases");
  expect(container.textContent).not.toContain("No saved encounters");

  const empty = await renderHome(handlerFor([], { encounters: [], total: 0, limit: 200 }));
  expect(empty.textContent).toContain("No published cases");
  expect(empty.textContent).toContain("No saved encounters");
  expect(empty.textContent).not.toContain("Loading published cases");
  expect(empty.textContent).not.toContain("Loading your encounters");

  const historyFailed = await renderHome(
    handlerFor([walter], { message: "Encounters could not be loaded.", errors: [], blockers: [] }, { encounters: 503 }),
  );
  expect(historyFailed.textContent).toContain("Walter Greene");
  expect(historyFailed.textContent).toContain("Encounters could not be loaded.");
  expect(historyFailed.textContent).not.toContain("No saved encounters");
  expect(historyFailed.textContent).not.toContain("Sam");

  const casesFailed = await renderHome(
    handlerFor({ message: "Cases could not be loaded.", errors: [], blockers: [] }, { encounters: [riley], total: 1, limit: 200 }, { cases: 503 }),
  );
  expect(casesFailed.textContent).toContain("Cases could not be loaded.");
  expect(casesFailed.textContent).toContain("Riley");
  expect(casesFailed.textContent).toContain("In progress");
  expect(casesFailed.textContent).not.toContain("Walter Greene, 72");
});
