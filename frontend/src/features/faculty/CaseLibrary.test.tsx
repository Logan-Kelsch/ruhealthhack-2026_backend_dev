import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import type { Go } from "../../app/types";
import { CaseLibrary } from "./CaseLibrary";
import { createApi } from "../../api/client";

const jordan = {
  case_id: "case_jordan_hale",
  version: 4,
  status: "draft" as const,
  title: "Jordan Hale: ankle sprain follow-up",
  golden: false,
  patient: "Jordan Hale",
  updated_at: "2026-03-02T15:04:00",
  blockers: ["Missing: What is the reason for the visit, as it would appear on the schedule?"],
};

const mina = {
  case_id: "case_mina_cho",
  version: 2,
  status: "published" as const,
  title: "Mina Cho: reflux after dinner",
  golden: true,
  patient: "Mina Cho",
  updated_at: "2026-01-15T08:00:00",
  blockers: [],
};

const mounts: Root[] = [];

afterEach(() => {
  for (const root of mounts) {
    act(() => root.unmount());
  }
  mounts.length = 0;
  document.body.innerHTML = "";
});

async function renderLibrary(
  handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
  go: Go = () => {},
) {
  const previous = globalThis.fetch;
  globalThis.fetch = handler as typeof fetch;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<CaseLibrary go={go} client={createApi("http://studio.test")} />);
  });
  // Let the load effect finish.
  await act(async () => {
    await Promise.resolve();
  });
  globalThis.fetch = previous;
  return container;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("loads and selects saved cases instead of sample rows", async () => {
  const visits: { screen: string; caseId?: string; version?: number; studioTab?: string }[] = [];
  const go: Go = (screen, opts) => {
    visits.push({ screen, caseId: opts?.caseId, version: opts?.version, studioTab: opts?.studioTab });
  };
  const container = await renderLibrary(async () => jsonResponse(200, [jordan, mina]), go);
  const text = container.textContent ?? "";

  expect(text).toContain("Jordan Hale");
  expect(text).toContain("Version 4");
  expect(text).toContain("Draft");
  expect(text).toContain("Mina Cho");
  expect(text).toContain("Version 2");
  expect(text).toContain("Published");
  expect(text).toContain("Mar 2, 2026");
  expect(text).not.toContain("Depression follow-up");
  expect(text).not.toContain("Dietetics student");

  const draftFilter = [...container.querySelectorAll("button")].find((button) => button.textContent === "Draft");
  await act(async () => {
    draftFilter?.click();
  });
  expect(container.textContent).toContain("Jordan Hale");
  expect(container.textContent).not.toContain("Mina Cho");

  const row = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Jordan Hale"));
  await act(async () => {
    row?.click();
  });
  expect(visits).toEqual([
    { screen: "f-studio", caseId: "case_jordan_hale", version: 4, studioTab: "tree" },
  ]);
});

test("loading, empty, and error states do not show sample cases", async () => {
  let release: (response: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  const previous = globalThis.fetch;
  globalThis.fetch = (() => pending) as unknown as typeof fetch;
  await act(async () => {
    root.render(<CaseLibrary go={() => {}} client={createApi("http://studio.test")} />);
  });
  expect(container.textContent).toContain("Loading saved cases");
  expect(container.textContent).not.toContain("Depression follow-up");
  expect(container.textContent).not.toContain("Jordan Hale");

  await act(async () => {
    release(jsonResponse(200, []));
    await pending;
  });
  expect(container.textContent).toContain("No saved cases");
  expect(container.textContent).not.toContain("Depression follow-up");
  expect(container.textContent).not.toContain("Walter Greene");
  globalThis.fetch = previous;
});

test("an API error shows the server message and no sample cases", async () => {
  const container = await renderLibrary(async () =>
    jsonResponse(503, { message: "Studio is down", errors: [], blockers: [] }),
  );
  expect(container.textContent).toContain("Studio is down");
  expect(container.textContent).not.toContain("Depression follow-up");
  expect(container.textContent).not.toContain("Walter Greene");
  expect(container.textContent).not.toContain("Jordan Hale");
});
