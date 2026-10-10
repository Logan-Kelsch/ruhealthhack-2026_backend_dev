import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type ErrorResponse = components["schemas"]["ErrorResponse"];
export type ErrorItem = components["schemas"]["ErrorItem"];
export type StudioCaseSummary = components["schemas"]["StudioCaseSummary"];

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
