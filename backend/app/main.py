from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import encounters, studio
from app.integrations import elevenlabs
from app.integrations.bedrock import llm_available
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

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Conflict)
    async def conflict(_: Request, exc: Conflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/config")
    def config() -> dict:
        """What the frontend needs to pick its voice path. No secrets."""
        return {
            "llm": llm_available(),
            "tts": elevenlabs.tts_available(),
            "stt_provider": settings.stt_provider,
            "stt_commit_silence_ms": settings.stt_commit_silence_ms,
        }

    app.include_router(encounters.router)
    app.include_router(studio.router)
    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/portraits", StaticFiles(directory=PORTRAITS_DIR), name="portraits")
    return app


app = create_app()
