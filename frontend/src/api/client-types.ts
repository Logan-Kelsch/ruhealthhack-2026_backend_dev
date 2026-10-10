import { createApi } from "./client";

// These calls are not executed. Type checking is what rejects a wrong path, body, or query.
export function rejectedByGeneratedTypes(client: ReturnType<typeof createApi>): void {
  // @ts-expect-error there is no such path on the API
  client.GET("/api/studio/not-a-route");
  // @ts-expect-error a draft description is text, not a number
  client.POST("/api/studio/drafts", { body: { description: 12 } });
  // @ts-expect-error health does not take a query
  client.GET("/api/health", { params: { query: { secret: "no" } } });
}
