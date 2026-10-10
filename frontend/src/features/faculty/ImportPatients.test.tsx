import { useState } from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import type { Go, ScreenId } from "../../app/types";
import { createApi, type ApiClient } from "../../api/client";
import { CaseLibrary } from "./CaseLibrary";
import { ImportPatients } from "./ImportPatients";

const dominic = {
  case_id: "dominic_rivera",
  version: 1,
  status: "draft" as const,
  title: "Dominic Rivera: Poorly controlled Type 2 Diabetes Mellitus",
  golden: false,
  patient: "Dominic Rivera",
  updated_at: "2026-04-02T12:00:00",
  blockers: ["66 facts still need approval."],
};

const yvette = {
  case_id: "yvette_armstrong",
  version: 1,
  status: "draft" as const,
  title: "Yvette Armstrong: Hypertension (Stage II)",
  golden: false,
  patient: "Yvette Armstrong",
  updated_at: "2026-04-02T12:00:01",
  blockers: ["76 facts still need approval."],
};

// Saved in the library only. If the screen reused the import payload, this name would not appear.
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
let restoreFetch: (() => void) | null = null;

afterEach(() => {
  restoreFetch?.();
  restoreFetch = null;
  for (const root of mounts) {
    act(() => root.unmount());
  }
  mounts.length = 0;
  document.body.innerHTML = "";
});

// A JSON response the shared client can read the same way the API writes one.
function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// Import, then the Case Library, using the same client the screens use.
function FacultyImportFlow({ client }: { client: ApiClient }) {
  const [screen, setScreen] = useState<ScreenId>("f-import");
  const go: Go = (next) => setScreen(next);
  if (screen === "f-cases") return <CaseLibrary go={go} client={client} />;
  return <ImportPatients go={go} client={client} />;
}

// Keep the stand-in fetch until the test ends, including the click that starts the import.
function installFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const previous = globalThis.fetch;
  // Bun's fetch has extra helpers. The stand-in only needs to answer requests.
  globalThis.fetch = handler as typeof fetch;
  restoreFetch = () => {
    globalThis.fetch = previous;
  };
}

// Render the import screen. Fetch must already be the stand-in.
async function renderFlow() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<FacultyImportFlow client={createApi("http://studio.test")} />);
  });
  return container;
}

// Find a control by the words a faculty member sees.
function buttonNamed(container: HTMLElement, label: string) {
  return [...container.querySelectorAll("button")].find((button) => button.textContent?.includes(label));
}

// openapi-fetch passes a Request, so the URL and method live on that object.
function describeCall(input: RequestInfo | URL, init?: RequestInit) {
  if (typeof input === "string" || input instanceof URL) {
    return { url: String(input), method: init?.method ?? "GET" };
  }
  return { url: input.url, method: init?.method ?? input.method };
}

test("imports the full sample set and the case library reloads saved records", async () => {
  const calls: { url: string; method: string }[] = [];
  installFetch(async (input, init) => {
    const { url, method } = describeCall(input, init);
    calls.push({ url, method });
    if (url.includes("/api/studio/import/vhs") && method === "POST") {
      return jsonResponse(201, { count: 2, cases: [dominic, yvette] });
    }
    if (url.endsWith("/api/studio/cases") && method === "GET") {
      return jsonResponse(200, [dominic, yvette, mina]);
    }
    return jsonResponse(500, { message: "Unexpected request", errors: [], blockers: [] });
  });
  const container = await renderFlow();

  const before = container.textContent ?? "";
  expect(before.toLowerCase()).toContain("sample set");
  expect(before).not.toContain("Open in Studio");
  expect(before).not.toContain("8 patients");
  expect(before).not.toContain("Walter Greene");
  expect(before).not.toContain("Dominic Rivera");

  await act(async () => {
    buttonNamed(container, "Import sample set")?.click();
  });
  await act(async () => {
    await Promise.resolve();
  });

  const imported = container.textContent ?? "";
  expect(imported).toContain("Imported 2 cases");
  expect(imported).toContain("Dominic Rivera");
  expect(imported).toContain("Yvette Armstrong");
  expect(imported).toContain("Draft");
  expect(imported).toContain("Needs faculty review");
  expect(imported).not.toContain("Walter Greene");
  expect(imported).not.toContain("Open in Studio");
  expect(calls.filter((call) => call.method === "POST")).toHaveLength(1);

  await act(async () => {
    buttonNamed(container, "View cases")?.click();
  });
  await act(async () => {
    await Promise.resolve();
  });

  const library = container.textContent ?? "";
  expect(library).toContain("Mina Cho");
  expect(library).toContain("Dominic Rivera");
  expect(library).toContain("Yvette Armstrong");
  expect(library).toContain("Published");
  expect(calls.some((call) => call.method === "GET" && call.url.endsWith("/api/studio/cases"))).toBe(true);
});

test("a failed import is shown once and is not recorded as complete", async () => {
  let posts = 0;
  installFetch(async (input, init) => {
    const { url, method } = describeCall(input, init);
    if (url.includes("/api/studio/import/vhs") && method === "POST") {
      posts += 1;
      return jsonResponse(500, {
        message: "The sponsor sample set could not be imported.",
        errors: [],
        blockers: [],
      });
    }
    return jsonResponse(500, { message: "Unexpected request", errors: [], blockers: [] });
  });
  const container = await renderFlow();

  await act(async () => {
    buttonNamed(container, "Import sample set")?.click();
  });
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });

  const text = container.textContent ?? "";
  expect(text).toContain("The sponsor sample set could not be imported.");
  expect(text).not.toContain("Imported");
  expect(text).not.toContain("Dominic Rivera");
  expect(text).not.toContain("Walter Greene");
  expect(posts).toBe(1);
});
