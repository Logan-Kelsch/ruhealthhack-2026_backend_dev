# HTTP API test runtime follow-up

Date: 2026-10-10. This is an addendum to the Notebook 01–07 reports; their original execution results remain unchanged. [Machine-readable results](http_api_runtime_followup.json) record the two environments separately.

The first HTTP test stalled on its first `client.get("/api/cases")`. A `faulthandler` dump located the caller inside Starlette `TestClient.handle_request`, waiting for AnyIO's blocking portal, while its event-loop thread was idle in `selectors.select`. The request did not reach an application assertion or produce an HTTP response.

Two minimal controls reproduced the stall in the restricted execution environment: a separate FastAPI app with one synchronous `GET /` route using `TestClient`, and `anyio.to_thread.run_sync(lambda: "ok")` with no project import. Both timed out after 8 seconds. A concurrent timer task allowed the AnyIO handoff to complete, which points to a thread-to-event-loop wakeup problem in that runtime. AF_INET socket creation was also denied there; that is an observed restriction, not established as the cause of this particular stall.

The same bare AnyIO handoff completed in the working execution environment. There, the existing project tests ran unchanged:

| Run | Passed | Failed | Uncompleted | Duration |
|---|---:|---:|---:|---:|
| `LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend/tests/test_api.py` | **7** | **0** | **0** | 1.05 s |
| `LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend/tests backend_kelsch/tests` | **76** | **0** | **0** | 6.82 s |

The earlier restricted run timed out after 25 seconds with 0/7 completed. The working run establishes that all seven HTTP tests pass on this code and dependency set; it does not establish live Bedrock, voice-provider, clinical, or learner-study performance. No backend defect was demonstrated, and no application code or Notebook 01–07 report was changed. If the stall appears in normal CI, record the Python, AnyIO, Starlette, event-loop and execution environment details before changing application behavior.
