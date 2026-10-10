import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, test } from "bun:test";
import { App } from "../../app/App";
import { createApi } from "../../api/client";

const DESCRIPTION = "A 58-year-old man with type 2 diabetes and high blood pressure.";

const nameGap = {
  id: "name",
  question: "What is the patient's name?",
  kind: "field" as const,
  blocking: true,
};

const allergyGap = {
  id: "allergies",
  question: 'Any allergies? If none, say "no known allergies".',
  kind: "facts" as const,
  blocking: false,
};

const createdDraft = {
  status: "draft" as const,
  llm_calls: [],
  blockers: ["Missing: What is the patient's name?"],
  gaps: [nameGap, allergyGap],
  case: {
    case_id: "case_jordan_hale",
    version: 4,
    status: "draft" as const,
    title: "New case (draft)",
    description: DESCRIPTION,
    profile: { name: "New patient", age: 58, sex: "male" as const },
    facts: [],
  },
};

const namedDraft = {
  status: "draft" as const,
  llm_calls: [],
  blockers: [],
  gaps: [allergyGap],
  case: {
    case_id: "case_jordan_hale",
    version: 4,
    status: "draft" as const,
    title: "New case (draft)",
    description: DESCRIPTION,
    profile: { name: "Jordan Hale", age: 58, sex: "male" as const },
    facts: [
      {
        id: "f_allergies_1",
        text: "No known allergies",
        status: "draft" as const,
        source: { kind: "faculty" as const, ref: "intake:allergies", by: null },
      },
    ],
  },
};

type Call = { url: string; method: string; body: unknown };

const mounts: Root[] = [];

afterEach(() => {
  for (const root of mounts) {
    act(() => root.unmount());
  }
  mounts.length = 0;
  document.body.innerHTML = "";
  window.history.replaceState(null, "", "/");
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

// A stand-in fetch that records the method, URL, and JSON body the screen sent.
function installFetch(handler: (url: string, method: string, body: unknown) => Promise<Response> | Response) {
  const calls: Call[] = [];
  const previous = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    // openapi-fetch passes a Request. The method and body live on it, not always on init.
    const method = init?.method ?? (input instanceof Request ? input.method : "GET");
    let raw = typeof init?.body === "string" ? init.body : "";
    if (!raw && input instanceof Request) raw = await input.clone().text();
    const body = raw ? JSON.parse(raw) : null;
    calls.push({ url, method, body });
    return handler(url, method, body);
  }) as typeof fetch;
  return {
    calls,
    restore() {
      globalThis.fetch = previous;
    },
  };
}

async function renderApp(href: string) {
  window.history.replaceState(null, "", href);
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounts.push(root);
  await act(async () => {
    root.render(<App client={createApi("http://studio.test")} />);
  });
  return container;
}

function heading(container: HTMLElement): string {
  return container.querySelector("h1")?.textContent ?? "";
}

function buttonNamed(container: HTMLElement, name: string): HTMLButtonElement {
  const found = [...container.querySelectorAll("button")].find((button) => button.textContent?.trim() === name);
  if (!found) throw new Error(`No button named ${name}`);
  return found as HTMLButtonElement;
}

function field(container: HTMLElement, id: string): HTMLTextAreaElement {
  const found = container.querySelector(`#${id}`);
  if (!found || found.tagName !== "TEXTAREA") throw new Error(`No text area #${id}`);
  return found as HTMLTextAreaElement;
}

async function typeIn(area: HTMLTextAreaElement, value: string) {
  await act(async () => {
    const prototype = Object.getPrototypeOf(area) as object;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    setter?.call(area, value);
    area.dispatchEvent(new Event("input", { bubbles: true }));
    area.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function click(button: HTMLButtonElement) {
  await act(async () => {
    button.click();
    await Promise.resolve();
  });
}

// Let the screen finish the request and the render that follows it.
async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

test("a description opens that draft and an answer stays on the returned case", async () => {
  const seen = installFetch((url, method) => {
    if (method === "POST" && url.endsWith("/api/studio/drafts")) return jsonResponse(201, createdDraft);
    if (method === "GET" && url.startsWith("http://studio.test/api/studio/cases/case_jordan_hale")) {
      return jsonResponse(200, {
        status: createdDraft.status,
        blockers: createdDraft.blockers,
        gaps: createdDraft.gaps,
        case: createdDraft.case,
      });
    }
    if (method === "POST" && url === "http://studio.test/api/studio/cases/case_jordan_hale/intake") {
      return jsonResponse(200, namedDraft);
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });

  try {
    const container = await renderApp("/#f-home");
    await click(buttonNamed(container, "New case"));
    expect(container.textContent).toContain("Describe the patient");
    expect(container.textContent).not.toContain("Epirocil");
    expect(container.textContent).not.toContain("Walter Greene, 72");

    await typeIn(field(container, "patient-description"), DESCRIPTION);
    await click(buttonNamed(container, "Create draft"));
    await settle();

    expect(window.location.hash).toBe("#f-studio");
    expect(window.location.search).toBe("?case=case_jordan_hale&version=4");
    expect(container.textContent).toContain("New patient");
    expect(container.textContent).toContain("Version 4");
    expect(container.textContent).toContain(DESCRIPTION);
    expect(container.textContent).toContain("What is the patient's name?");
    expect(container.textContent).toContain('Any allergies? If none, say "no known allergies".');
    expect(container.textContent).toContain("2 intake questions still open");
    expect(container.textContent).toContain("1 required question still open");
    expect(container.textContent).toContain("Missing: What is the patient's name?");
    expect(seen.calls.filter((call) => call.method === "POST" && call.url.endsWith("/api/studio/drafts"))).toHaveLength(1);
    expect(seen.calls.some((call) => call.method === "GET" && call.url.includes("version=4"))).toBe(true);

    await typeIn(field(container, "gap-name"), "Jordan Hale");
    await click(buttonNamed(container, "Save answer"));
    await settle();

    const intake = seen.calls.filter((call) => call.url.endsWith("/intake"));
    expect(intake).toEqual([
      {
        url: "http://studio.test/api/studio/cases/case_jordan_hale/intake",
        method: "POST",
        body: { gap_id: "name", text: "Jordan Hale" },
      },
    ]);
    expect(container.textContent).toContain("Jordan Hale");
    expect(container.textContent).not.toContain("What is the patient's name?");
    expect(container.textContent).toContain('Any allergies? If none, say "no known allergies".');
    expect(container.textContent).toContain("1 intake question still open");
    expect(container.textContent).toContain("Required intake questions are answered");
    expect(window.location.search).toBe("?case=case_jordan_hale&version=4");
    expect(seen.calls.filter((call) => call.url.endsWith("/api/studio/drafts"))).toHaveLength(1);
  } finally {
    seen.restore();
  }
});

const savedDetail = {
  status: createdDraft.status,
  blockers: createdDraft.blockers,
  gaps: createdDraft.gaps,
  case: createdDraft.case,
};

test("a failed description is not saved and retry is explicit", async () => {
  let release: (response: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  let posts = 0;
  const seen = installFetch((url, method) => {
    if (method === "POST" && url.endsWith("/api/studio/drafts")) {
      posts += 1;
      if (posts === 1) return pending;
      return jsonResponse(201, createdDraft);
    }
    if (method === "GET") return jsonResponse(200, savedDetail);
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });

  try {
    const container = await renderApp("/#f-home");
    await click(buttonNamed(container, "New case"));
    await typeIn(field(container, "patient-description"), DESCRIPTION);
    await click(buttonNamed(container, "Create draft"));
    expect(container.textContent).toContain("Saving draft");
    expect(window.location.search).toBe("");
    expect(heading(container)).toBe("New case");

    await act(async () => {
      release(jsonResponse(422, { message: "String should have at least 10 characters", errors: [], blockers: [] }));
      await pending;
    });
    await settle();
    expect(container.textContent).toContain("String should have at least 10 characters");
    expect(heading(container)).toBe("New case");
    expect(container.textContent).not.toContain("New patient");
    expect(field(container, "patient-description").value).toBe(DESCRIPTION);
    expect(window.location.search).toBe("");
    expect(posts).toBe(1);

    await click(buttonNamed(container, "Try again"));
    await settle();
    expect(posts).toBe(2);
    expect(window.location.search).toBe("?case=case_jordan_hale&version=4");
    expect(heading(container)).toBe("New patient");
  } finally {
    seen.restore();
  }
});

test("a failed answer is not saved and retry is explicit", async () => {
  let release: (response: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  let intakePosts = 0;
  const seen = installFetch((url, method) => {
    if (method === "GET") return jsonResponse(200, savedDetail);
    if (method === "POST" && url.endsWith("/intake")) {
      intakePosts += 1;
      if (intakePosts === 1) return pending;
      return jsonResponse(200, namedDraft);
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });

  try {
    const container = await renderApp("/?case=case_jordan_hale&version=4#f-studio");
    await settle();
    expect(heading(container)).toBe("New patient");
    expect(seen.calls.some((call) => call.url.endsWith("/api/studio/drafts"))).toBe(false);

    await typeIn(field(container, "gap-name"), "Jordan Hale");
    await click(buttonNamed(container, "Save answer"));
    expect(container.textContent).toContain("Saving answer");
    expect(heading(container)).toBe("New patient");

    await act(async () => {
      release(jsonResponse(503, { message: "Could not save the answer", errors: [], blockers: [] }));
      await pending;
    });
    await settle();
    expect(container.textContent).toContain("Could not save the answer");
    expect(heading(container)).toBe("New patient");
    expect(container.textContent).toContain("What is the patient's name?");
    expect(field(container, "gap-name").value).toBe("Jordan Hale");
    expect(intakePosts).toBe(1);

    await click(buttonNamed(container, "Try again"));
    await settle();
    expect(intakePosts).toBe(2);
    expect(heading(container)).toBe("Jordan Hale");
    expect(container.textContent).not.toContain("What is the patient's name?");
    expect(seen.calls.filter((call) => call.url.endsWith("/api/studio/drafts"))).toHaveLength(0);
  } finally {
    seen.restore();
  }
});

test("refresh loads the saved draft and does not create another case", async () => {
  const seen = installFetch((url, method) => {
    if (method === "GET" && url === "http://studio.test/api/studio/cases/case_jordan_hale?version=4") {
      return jsonResponse(200, savedDetail);
    }
    return jsonResponse(500, { message: `unexpected ${method} ${url}`, errors: [], blockers: [] });
  });

  try {
    const container = await renderApp("/?case=case_jordan_hale&version=4#f-studio");
    await settle();
    expect(heading(container)).toBe("New patient");
    expect(container.textContent).toContain("What is the patient's name?");
    expect(container.textContent).toContain("Version 4");
    expect(seen.calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      "GET http://studio.test/api/studio/cases/case_jordan_hale?version=4",
    ]);
    expect(window.location.search).toBe("?case=case_jordan_hale&version=4");
  } finally {
    seen.restore();
  }
});
