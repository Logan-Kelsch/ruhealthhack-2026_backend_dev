"""Turn FastAPI and application failures into one error body.

Callers keep the status code they already used. The body keeps the message,
the validation location, and any publish blockers instead of nesting them under
different keys.
"""

import json

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.http import ErrorItem, ErrorResponse
from app.services import Conflict, NotFound

# Routes that already return these statuses. The schema should name the same body the handler sends.
SHARED_ERROR_RESPONSES = {
    ("/api/studio/cases/{case_id}", "get"): {404: "No saved case with that id."},
    ("/api/studio/cases/{case_id}", "put"): {
        404: "No saved case with that id.",
        409: "A fact is still referenced.",
    },
    ("/api/studio/cases/{case_id}/intake", "post"): {404: "No saved case with that id."},
    ("/api/studio/cases/{case_id}/approve", "post"): {404: "No saved case with that id."},
    ("/api/studio/cases/{case_id}/autofill", "post"): {404: "No saved case with that id."},
    ("/api/studio/cases/{case_id}/consistency", "get"): {404: "No saved case with that id."},
    ("/api/studio/cases/{case_id}/consistency/{finding_id}/dismiss", "post"): {
        404: "The case or finding was not found.",
    },
    ("/api/studio/cases/{case_id}/preview", "post"): {404: "The case or visit was not found."},
    ("/api/studio/cases/{case_id}/publish", "post"): {
        404: "No saved case with that id.",
        409: "The case is not ready to publish.",
    },
    ("/api/studio/import/vhs", "post"): {500: "The sponsor sample set could not be imported."},
    ("/api/cases/{case_id}", "get"): {404: "No published case with that id."},
    ("/api/encounters", "post"): {404: "The case or visit was not found.", 409: "The encounter cannot be started."},
    ("/api/encounters/{enc_id}", "get"): {404: "No saved encounter with that id."},
    ("/api/encounters/{enc_id}/utterances", "post"): {404: "No saved encounter with that id.", 409: "The encounter is not accepting a turn."},
    ("/api/encounters/{enc_id}/end", "post"): {404: "No saved encounter with that id."},
    ("/api/stt/token", "post"): {
        409: "Speech transcription is not configured.",
        503: "The transcription service did not provide a token.",
    },
}


def error_response(status_code: int, body: ErrorResponse) -> JSONResponse:
    """Send the shared error body with the status the route already chose."""
    return JSONResponse(status_code=status_code, content=body.model_dump())


def from_validation(exc: RequestValidationError) -> ErrorResponse:
    """Keep each field path and message. Drop the submitted input so a body is not echoed back."""
    items: list[ErrorItem] = []
    for problem in exc.errors():
        loc: list[str | int] = []
        for part in problem.get("loc", ()):
            # loc parts are field names or list indexes. Anything else is still shown as text.
            loc.append(part if isinstance(part, (str, int)) else str(part))
        items.append(ErrorItem(loc=loc, msg=str(problem.get("msg", "")), type=problem.get("type")))
    message = items[0].msg if items else "Request validation failed"
    return ErrorResponse(message=message, errors=items)


def from_http_exception(exc: HTTPException) -> ErrorResponse:
    """Read a string detail, or a payload that already carries a message, errors, and blockers."""
    detail = exc.detail
    if isinstance(detail, dict) and "message" in detail:
        blockers = detail.get("blockers") or []
        raw_errors = detail.get("errors") or []
        # Field errors stay structured so a screen can point at the fact that is still in use.
        errors = [ErrorItem.model_validate(item) for item in raw_errors]
        return ErrorResponse(
            message=str(detail["message"]),
            blockers=[str(item) for item in blockers],
            errors=errors,
        )
    return ErrorResponse(message=str(detail))


async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Validation stays 422. The location of the bad field remains in errors."""
    return error_response(422, from_validation(exc))


async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    """Keep the status a route raised, and put its message in the shared body."""
    return error_response(exc.status_code, from_http_exception(exc))


async def handle_not_found(_: Request, exc: NotFound) -> JSONResponse:
    """A missing case or encounter stays 404."""
    return error_response(404, ErrorResponse(message=str(exc)))


async def handle_conflict(_: Request, exc: Conflict) -> JSONResponse:
    """A state conflict, such as speaking after an encounter ended, stays 409."""
    return error_response(409, ErrorResponse(message=str(exc)))


def _error_response_doc(description: str) -> dict:
    """OpenAPI response object pointing at the shared error body."""
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
    }


def publish_shared_errors(schema: dict) -> dict:
    """Replace FastAPI's default validation schema so generated clients see one error body."""
    raw = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
    definitions = raw.pop("$defs", {})
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components["ErrorResponse"] = raw
    for name, body in definitions.items():
        components[name] = body

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"} or not isinstance(operation, dict):
                continue
            responses = operation.setdefault("responses", {})
            # Every body or query that FastAPI can reject already has a 422 entry.
            if "422" in responses:
                responses["422"] = _error_response_doc("Validation error")
            for status, description in SHARED_ERROR_RESPONSES.get((path, method), {}).items():
                responses[str(status)] = _error_response_doc(description)

    # The old validation components are unused once every 422 points at ErrorResponse.
    referenced = json.dumps(schema.get("paths", {}))
    for name in ("HTTPValidationError", "ValidationError"):
        if f"#/components/schemas/{name}" not in referenced:
            components.pop(name, None)
    return schema
