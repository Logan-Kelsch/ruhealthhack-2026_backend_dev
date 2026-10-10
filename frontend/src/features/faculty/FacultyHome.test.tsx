import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import { createApi } from "../../api/client";
import type { Go } from "../../app/types";
import { FacultyHome } from "./FacultyHome";

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
  encounter_id: "enc_riley",
  case_id: "alina_reyes",
  visit_id: "v1",
  student_name: "Riley",
  status: "active" as const,
  started_at: "2026-10-10T16:00:00Z",
  rubric_total: null,
  review_flag: false,
  previous_encounter_id: null,
  patient_name: "Alina Reyes",
  case_title: "Alina Reyes: low mood, and what the questionnaire hides",
  visit_label: "First visit",
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

async function renderHome(
  handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
  go: Go = () => {},
) {
  const client = createApi("http://review.test", handler as typeof fetch);
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<FacultyHome go={go} client={client} />);
  });
  await act(async () => {
    await Promise.resolve();
  });
  return container;
}

test("the review list shows saved encounters and opens one", async () => {
  const visits: { screen: string; encounterId?: string | null }[] = [];
  const go: Go = (screen, opts) => {
    visits.push({ screen, encounterId: opts?.encounterId });
  };
  const container = await renderHome(async () => {
    return jsonResponse(200, { encounters: [sam, riley], total: 2, limit: 200 });
  }, go);
  const text = container.textContent ?? "";

  expect(text).toContain("Sam");
  expect(text).toContain("Walter Greene");
  expect(text).toContain("First visit");
  expect(text).toContain("Complete");
  expect(text).toContain("Needs review");
  expect(text).toContain("10");
  expect(text).toContain("Riley");
  expect(text).toContain("Alina Reyes");
  expect(text).toContain("In progress");
  expect(text).toContain("2 saved encounters");
  expect(text).not.toContain("Showing 2 of 2");
  expect(text).not.toContain("Due ");
  expect(text).not.toContain("Class average");
  expect(text).not.toContain("assigned");
  expect(text).not.toContain("recommendation");
  expect(text).not.toContain("Student 14");

  const review = [...container.querySelectorAll("button")].find((button) => button.textContent === "Review" && button.closest("div")?.textContent?.includes("Sam"));
  await act(async () => {
    review?.click();
  });
  expect(visits).toEqual([{ screen: "f-review", encounterId: "enc_sam" }]);
});

test("a short list says how many saved encounters were left out", async () => {
  const container = await renderHome(async () => jsonResponse(200, { encounters: [sam], total: 2, limit: 1 }));
  expect(container.textContent).toContain("Showing 1 of 2");
  expect(container.textContent).toContain("Sam");
  expect(container.textContent).not.toContain("Riley");
  expect(container.textContent).not.toContain("2 saved encounters");
});

test("loading, empty, and error states stay distinct", async () => {
  let release: (response: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const client = createApi("http://review.test", (async (_input: RequestInfo | URL) => pending) as typeof fetch);
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<FacultyHome go={() => {}} client={client} />);
  });
  expect(container.textContent).toContain("Loading saved encounters");
  expect(container.textContent).not.toContain("Sam");
  expect(container.textContent).not.toContain("No saved encounters");

  await act(async () => {
    release(jsonResponse(200, { encounters: [], total: 0, limit: 200 }));
    await pending;
  });
  expect(container.textContent).toContain("No saved encounters");
  expect(container.textContent).not.toContain("Loading saved encounters");
  expect(container.textContent).not.toContain("Student 14");

  const failed = await renderHome(async () => jsonResponse(503, { message: "Encounters could not be loaded.", errors: [], blockers: [] }));
  expect(failed.textContent).toContain("Encounters could not be loaded.");
  expect(failed.textContent).not.toContain("No saved encounters");
  expect(failed.textContent).not.toContain("Loading saved encounters");
  expect(failed.textContent).not.toContain("Sam");
});
