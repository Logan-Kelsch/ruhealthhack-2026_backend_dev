import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type ErrorResponse = components["schemas"]["ErrorResponse"];
export type ErrorItem = components["schemas"]["ErrorItem"];
export type StudioCaseSummary = components["schemas"]["StudioCaseSummary"];
export type StudioCaseDetail = components["schemas"]["StudioCaseDetail"];
export type StudioDraftResult = components["schemas"]["StudioDraftResult"];
export type IntakeGap = components["schemas"]["IntakeGap"];

// One error for every failed response, so screens do not each invent a fallback.
export class ApiError extends Error {
  readonly status: number;
  readonly blockers: string[];
  readonly errors: ErrorItem[];

  constructor(status: number, body: ErrorResponse) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.blockers = body.blockers ?? [];
    this.errors = body.errors ?? [];
  }
}

// baseUrl is empty in the app (same origin, or the Vite proxy) and set in tests.
export function createApi(baseUrl = "") {
  return createClient<paths>({ baseUrl });
}

export const api = createApi();

export type ApiClient = ReturnType<typeof createApi>;

// Accept only the shared error body. Anything else becomes a plain failure message.
function isErrorBody(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null || !("message" in value)) {
    return false;
  }
  return typeof value.message === "string";
}

// openapi-fetch puts the JSON body on `error` for any status that is not a success.
export function asApiError(status: number, error: unknown): ApiError {
  if (isErrorBody(error)) {
    return new ApiError(status, {
      message: error.message,
      errors: error.errors ?? [],
      blockers: error.blockers ?? [],
    });
  }
  const message = typeof error === "string" && error.trim() ? error : "Request failed";
  return new ApiError(status, { message, errors: [], blockers: [] });
}

// A missing success body is a failure. Callers then show the shared error instead of inventing a case.
function unwrap<T>(status: number, data: T | undefined, error: unknown): T {
  if (data === undefined) throw asApiError(status, error);
  return data;
}

// Faculty description in, one saved draft out. The case id and version come from the response.
export async function createDraft(client: ApiClient, description: string): Promise<StudioDraftResult> {
  const result = await client.POST("/api/studio/drafts", { body: { description } });
  return unwrap(result.response.status, result.data, result.error);
}

// Read a saved version. This does not create a case; refresh uses it to restore the draft.
export async function loadStudioCase(
  client: ApiClient,
  caseId: string,
  version?: number,
): Promise<StudioCaseDetail> {
  const result = await client.GET("/api/studio/cases/{case_id}", {
    params: {
      path: { case_id: caseId },
      ...(version === undefined ? {} : { query: { version } }),
    },
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Send one answer to the gap the faculty member is looking at, then return the updated draft.
export async function answerIntake(
  client: ApiClient,
  caseId: string,
  gapId: string,
  text: string,
): Promise<StudioDraftResult> {
  const result = await client.POST("/api/studio/cases/{case_id}/intake", {
    params: { path: { case_id: caseId } },
    body: { gap_id: gapId, text },
  });
  return unwrap(result.response.status, result.data, result.error);
}
