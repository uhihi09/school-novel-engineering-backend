from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

# Project root (…/School_hackathon_backend), derived from this file's location so the
# default DB path works on any clone/machine. Override via the DATABASE_URL env var.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "School Hackathon Backend"
    
    # GCP / Vertex AI settings
    GCP_PROJECT_ID: Optional[str] = None
    GCP_LOCATION: str = "asia-northeast3"
    
    # Gemini API Key (for direct Google GenAI SDK usage)
    GEMINI_API_KEY: Optional[str] = None

    # Toggle Vertex AI backend for Gemini (requires GOOGLE_APPLICATION_CREDENTIALS + GCP_PROJECT_ID).
    # When false, the direct google-genai SDK is used with GEMINI_API_KEY (or mock fallback if absent).
    USE_VERTEX_AI: bool = False

    # Gemini model ids (centralized so they can be swapped per environment)
    GEMINI_FLASH_MODEL: str = "gemini-3.5-flash"
    GEMINI_PRO_MODEL: str = "gemini-2.5-pro"
    GEMINI_TTS_MODEL: str = "gemini-2.5-flash-preview-tts"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"

    # Local directory where uploaded citizen-report media is stored and served from /media.
    MEDIA_DIR: str = "media"

    # GCP Cloud Storage bucket for uploaded citizen-report media (F-2/F-6)
    GCS_BUCKET: str = "school_hackathon"

    # DB Settings (Using SQLite as a mock for Spanner during local/hackathon testing)
    DATABASE_URL: str = f"sqlite:///{_PROJECT_ROOT / 'equiscope.db'}"
    
    # JWT security
    SECRET_KEY: str = "supersecret_equiscope_key_change_me_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
