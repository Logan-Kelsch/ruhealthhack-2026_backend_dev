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
    # The team's shared laptop key (infra/README.md). pydantic-settings does not export .env to
    # the process environment, so boto3 only sees these when passed explicitly. Left out on the
    # server, which uses its instance role.
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    # Set LLM_ENABLED=false to run fully offline (keyword classifier + template replies).
    llm_enabled: bool = True
    bedrock_model_fast: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_model_strong: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    llm_timeout_s: float = 20.0

    elevenlabs_api_key: str | None = None
    elevenlabs_tts_model_live: str = "eleven_turbo_v2_5"
    elevenlabs_default_voice_id: str | None = None
    # Scribe v2 Realtime. The browser connects with a single-use token, not this key.
    elevenlabs_stt_model: str = "scribe_v2_realtime"
    # Only turn on for models that support inline audio tags such as [sighs].
    elevenlabs_audio_tags: bool = False

    # Silence that makes Scribe commit a turn, and how sure the detector must be.
    # ElevenLabs takes the silence value in seconds.
    stt_vad_silence_secs: float = 1.2
    stt_vad_threshold: float = 0.4

    nlm_lookup_enabled: bool = True
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def aws_session():
    """boto3 session from settings: shared key, else AWS_PROFILE, else the default chain."""
    import boto3

    s = get_settings()
    if s.aws_access_key_id and s.aws_secret_access_key:
        return boto3.Session(
            aws_access_key_id=s.aws_access_key_id,
            aws_secret_access_key=s.aws_secret_access_key,
            region_name=s.aws_region,
        )
    return boto3.Session(profile_name=s.aws_profile or None, region_name=s.aws_region)
