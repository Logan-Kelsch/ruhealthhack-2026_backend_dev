import { expect, test } from "bun:test";
import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { asApiError, createApi } from "./client";

const publishBlock = {
  message: "This case is not ready to publish.",
  errors: [],
  blockers: ["Missing: What is the patient's name?"],
};

const validationProblem = {
  message: "String should have at least 10 characters",
  errors: [
    {
      loc: ["body", "description"],
      msg: "String should have at least 10 characters",
      type: "string_too_short",
    },
  ],
  blockers: [],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("shared client reads publish blockers from the standardized error", async () => {
  const client = createClient<paths>({
    baseUrl: "http://studio.test",
    fetch: async () => jsonResponse(409, publishBlock),
  });
  const result = await client.POST("/api/studio/cases/{case_id}/publish", {
    params: { path: { case_id: "case_jordan_hale" } },
  });

  const error = asApiError(result.response.status, result.error);
  expect(error.status).toBe(409);
  expect(error.message).toBe("This case is not ready to publish.");
  expect(error.blockers).toEqual(["Missing: What is the patient's name?"]);
  expect(error.errors).toEqual([]);
});

test("shared client keeps a validation location", async () => {
  const original = globalThis.fetch;
  // The client reads fetch when it is created, so the stand-in has to be in place first.
  globalThis.fetch = (async () => jsonResponse(422, validationProblem)) as unknown as typeof fetch;
  const client = createApi("http://studio.test");
  try {
    const result = await client.POST("/api/studio/drafts", {
      body: { description: "A 58-year-old man with type 2 diabetes and high blood pressure." },
    });
    const error = asApiError(result.response.status, result.error);
    expect(error.status).toBe(422);
    expect(error.message).toBe("String should have at least 10 characters");
    expect(error.errors).toEqual([
      {
        loc: ["body", "description"],
        msg: "String should have at least 10 characters",
        type: "string_too_short",
      },
    ]);
  } finally {
    globalThis.fetch = original;
  }
});
