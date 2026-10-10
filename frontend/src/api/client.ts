import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type ErrorResponse = components["schemas"]["ErrorResponse"];
export type ErrorItem = components["schemas"]["ErrorItem"];
export type StudioCaseSummary = components["schemas"]["StudioCaseSummary"];
export type StudioCaseDetail = components["schemas"]["StudioCaseDetail"];
export type StudioDraftResult = components["schemas"]["StudioDraftResult"];
export type StudioAutofillResult = components["schemas"]["StudioAutofillResult"];
export type StudioVocab = components["schemas"]["StudioVocab"];
export type ConsistencyFinding = components["schemas"]["ConsistencyFinding"];
export type PreviewRun = components["schemas"]["PreviewRun"];
export type PreviewRequest = components["schemas"]["Preview"];
export type Icd10Match = components["schemas"]["Icd10Match"];
export type IntakeGap = components["schemas"]["IntakeGap"];
export type VhsImportResponse = components["schemas"]["VhsImportResponse"];
export type CaseDocument = components["schemas"]["Case"];
export type ApprovalGroup = components["schemas"]["Approve"]["group"];
export type ItemStatus = "draft" | "approved";
export type PublicCase = components["schemas"]["PublicCase"];
export type PublicEncounter = components["schemas"]["PublicEncounter"];
export type PublicChartEntry = components["schemas"]["PublicChartEntry"];

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
// fetchImpl lets a test stand in for the network without replacing the global fetch.
export function createApi(baseUrl = "", fetchImpl?: typeof fetch) {
  if (fetchImpl) {
    return createClient<paths>({ baseUrl, fetch: fetchImpl });
  }
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

// Replace the saved draft with the case the faculty member edited. The response is what a refresh loads.
export async function saveStudioCase(
  client: ApiClient,
  caseId: string,
  caseDocument: CaseDocument,
): Promise<StudioCaseDetail> {
  const result = await client.PUT("/api/studio/cases/{case_id}", {
    params: { path: { case_id: caseId } },
    body: caseDocument,
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Change review state through the approval operation. keys names the items; the group says which list.
export async function setItemApproval(
  client: ApiClient,
  caseId: string,
  group: ApprovalGroup,
  status: ItemStatus,
  keys: string[],
): Promise<StudioCaseDetail> {
  const result = await client.POST("/api/studio/cases/{case_id}/approve", {
    params: { path: { case_id: caseId } },
    body: { group, status, keys },
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Ask for proposed labs and vitals. The case comes back with those drafts and the notes that explain them.
export async function autofillStudioCase(
  client: ApiClient,
  caseId: string,
  panels: string[],
  vitals: boolean,
): Promise<StudioAutofillResult> {
  const result = await client.POST("/api/studio/cases/{case_id}/autofill", {
    params: { path: { case_id: caseId } },
    body: { panels, vitals },
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Closed lists for topics, actions, exam maneuvers, and lab panels.
export async function loadStudioVocab(client: ApiClient): Promise<StudioVocab> {
  const result = await client.GET("/api/studio/vocab");
  return unwrap(result.response.status, result.data, result.error);
}

// Findings from the consistency rules. Dismissal is a separate save, so this list can be read again after refresh.
export async function loadConsistency(client: ApiClient, caseId: string): Promise<ConsistencyFinding[]> {
  const result = await client.GET("/api/studio/cases/{case_id}/consistency", {
    params: { path: { case_id: caseId } },
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Mark one finding as intended. The returned case is the saved draft, including that dismissal.
export async function dismissFinding(client: ApiClient, caseId: string, findingId: string): Promise<StudioCaseDetail> {
  const result = await client.POST("/api/studio/cases/{case_id}/consistency/{finding_id}/dismiss", {
    params: { path: { case_id: caseId, finding_id: findingId } },
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Run the selected test student against the saved draft. The transcript is the run that came back.
export async function previewStudioCase(
  client: ApiClient,
  caseId: string,
  body: PreviewRequest,
): Promise<PreviewRun> {
  const result = await client.POST("/api/studio/cases/{case_id}/preview", {
    params: { path: { case_id: caseId } },
    body,
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Ask the server to publish. A rejection throws, so the caller does not treat blockers as a saved version.
export async function publishStudioCase(client: ApiClient, caseId: string): Promise<StudioCaseDetail> {
  const result = await client.POST("/api/studio/cases/{case_id}/publish", {
    params: { path: { case_id: caseId } },
  });
  return unwrap(result.response.status, result.data, result.error);
}

// Diagnosis matches from the existing lookup. The caller decides what to store.
export async function lookupDiagnosis(client: ApiClient, query: string): Promise<Icd10Match[]> {
  const result = await client.GET("/api/studio/lookup/icd10", {
    params: { query: { q: query } },
  });
  return unwrap(result.response.status, result.data, result.error);
}
