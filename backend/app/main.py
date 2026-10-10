from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import demo, encounters, studio
from app.api.errors import (
    handle_conflict,
    handle_http_exception,
    handle_not_found,
    handle_validation,
    publish_shared_errors,
)
from app.integrations import elevenlabs
from app.integrations.bedrock import llm_available
from app.schemas.http import HealthResponse, PublicConfig
from app.services import Conflict, NotFound
from app.settings import BACKEND_DIR, get_settings

PORTRAITS_DIR = BACKEND_DIR / "app" / "data" / "portraits"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="[Product name] API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # One body for every application and validation error. Status codes stay as they were.
    app.add_exception_handler(RequestValidationError, handle_validation)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(NotFound, handle_not_found)
    app.add_exception_handler(Conflict, handle_conflict)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Lets a laptop or deploy check that the API process is up."""
        return HealthResponse(ok=True)

    @app.get("/api/config", response_model=PublicConfig)
    def config() -> PublicConfig:
        """What the browser needs to open Scribe. The long-lived key is not included."""
        # Read settings on each request so a changed environment is what the client sees.
        current = get_settings()
        return PublicConfig(
            llm=llm_available(),
            tts=elevenlabs.tts_available(),
            stt_provider="elevenlabs",
            stt_model_id=current.elevenlabs_stt_model,
            voice_id=current.elevenlabs_default_voice_id,
            tts_model_id=current.elevenlabs_tts_model_live,
            vad_silence_secs=current.stt_vad_silence_secs,
            vad_threshold=current.stt_vad_threshold,
            commit_strategy="vad",
            include_timestamps=True,
        )

    app.include_router(encounters.router)
    app.include_router(studio.router)
    app.include_router(demo.router)
    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/portraits", StaticFiles(directory=PORTRAITS_DIR), name="portraits")

    def openapi() -> dict:
        """Schema for export. Building it does not serve a request or open the database."""
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        app.openapi_schema = publish_shared_errors(schema)
        return app.openapi_schema

    app.openapi = openapi
    return app


app = create_app()
