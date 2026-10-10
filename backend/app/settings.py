"""All configuration comes from environment variables (.env). No secrets in code."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://rounds:rounds@localhost:5433/rounds"

    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    # Set LLM_ENABLED=false to run fully offline (keyword classifier + template replies).
    llm_enabled: bool = True
    bedrock_model_fast: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_model_strong: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    llm_timeout_s: float = 20.0

    elevenlabs_api_key: str | None = None
    elevenlabs_tts_model_live: str = "eleven_turbo_v2_5"
    elevenlabs_default_voice_id: str | None = None
    # Only turn on for models that support inline audio tags such as [sighs].
    elevenlabs_audio_tags: bool = False

    # Speech-to-text runs in the browser in V1 (Web Speech API). Silence before an
    # utterance is committed, mirrored by the frontend.
    stt_provider: str = "browser"
    stt_commit_silence_ms: int = 1200

    nlm_lookup_enabled: bool = True
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
