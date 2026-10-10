/** Opt-in presenter playback transport. It never starts a graded encounter. */
import { asApiError, type ApiClient } from "./client";
import type { components } from "./schema";

export type DemoSession = components["schemas"]["DemoSession"];
export type DemoTurnRequest = components["schemas"]["DemoTurnRequest"];
export type DemoTurnResult = components["schemas"]["DemoTurnResult"];
export type DemoPreparation = components["schemas"]["Preparation"];
export type DemoDebrief = components["schemas"]["DemoDebrief"];

function body<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) throw asApiError(result.response.status, result.error);
  return result.data;
}

export function scriptedDemo(client: ApiClient) {
  return {
    async scenarios() {
      return body(await client.GET("/api/demo/educator/scenarios"));
    },
    async prepare(scenarioId: number, description: string): Promise<DemoPreparation> {
      return body(await client.POST("/api/demo/educator/preparations", {
        body: { scenario_id: scenarioId, description },
      }));
    },
    async start(preparationId: string): Promise<DemoSession> {
      return body(await client.POST("/api/demo/sessions", {
        body: { preparation_id: preparationId, accept_fixed_script: true },
      }));
    },
    async read(sessionId: string): Promise<DemoSession> {
      return body(await client.GET("/api/demo/sessions/{sid}", {
        params: { path: { sid: sessionId } },
      }));
    },
    // Keep the same request_id AND body when retrying after a network failure.
    async turn(sessionId: string, request: DemoTurnRequest): Promise<DemoTurnResult> {
      return body(await client.POST("/api/demo/sessions/{sid}/turns", {
        params: { path: { sid: sessionId } }, body: request,
      }));
    },
    async end(sessionId: string): Promise<DemoSession> {
      return body(await client.POST("/api/demo/sessions/{sid}/end", {
        params: { path: { sid: sessionId } },
      }));
    },
    async debrief(sessionId: string): Promise<DemoDebrief> {
      return body(await client.GET("/api/demo/sessions/{sid}/debrief", {
        params: { path: { sid: sessionId } },
      }));
    },
  };
}
