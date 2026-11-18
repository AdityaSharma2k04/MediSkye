import json
import os
import tempfile
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Load root .env file if available
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


def normalize_async_database_url(url: str) -> str:
    """
    Normalizes a Postgres/Neon database URL for SQLAlchemy + asyncpg:
    1. Replaces postgres:// or postgresql:// with postgresql+asyncpg://
    2. Strips unsupported query parameters (e.g. channel_binding)
    3. Normalizes sslmode to ssl=require
    """
    if not url:
        return url

    s = str(url).strip()
    if s.startswith("postgres://"):
        s = "postgresql+asyncpg://" + s[len("postgres://"):]
    elif s.startswith("postgresql://"):
        s = "postgresql+asyncpg://" + s[len("postgresql://"):]

    if not s.startswith("postgresql+asyncpg://"):
        return s

    import urllib.parse
    parsed = urllib.parse.urlsplit(s)
    if not parsed.query:
        return s

    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_params = []

    for k, v in query_params:
        k_lower = k.lower()
        if k_lower == "channel_binding":
            # asyncpg does not support channel_binding
            continue
        elif k_lower == "statement_cache_size":
            # statement_cache_size must be configured in connect_args, not in the query string
            continue
        elif k_lower == "sslmode":
            # Convert sslmode to ssl=require
            filtered_params.append(("ssl", "require"))
        elif k_lower == "ssl":
            filtered_params.append((k, v))
        else:
            filtered_params.append((k, v))

    new_query = urllib.parse.urlencode(filtered_params)
    normalized = urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        new_query,
        parsed.fragment
    ))
    return normalized


class Settings(BaseSettings):
    PROJECT_NAME: str = "MediSkye AI Medical Assistant"
    VERSION: str = "2.0.0"
    API_V1_STR: str = ""

    # Environment
    ENV: str = "production"
    DEBUG: bool = False

    @property
    def ENVIRONMENT(self) -> str:
        return self.ENV

    # Database & Redis
    DATABASE_URL: str = "sqlite+aiosqlite:///./mediskye.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security & API Key
    ALLOW_UNVERIFIED_JWT_FALLBACK: bool = False
    CACHE_WARM_RETRY_DELAY_SECONDS: float = 2.0
    GOOGLE_API_KEY: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    GEMINI_MODEL: str = "gemini-3.8-flash"
    PRIMARY_CHAT_MODEL: str = "gemini-3.8-flash"
    PRIMARY_METRICS_MODEL: str = "gemini-3.8-flash"
    PRIMARY_SUMMARY_MODEL: str = "gemini-3.6-flash"
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    MODEL_FALLBACK_CHAIN: list[str] = [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ]
    GEMINI_FALLBACK_MODELS: list[str] = [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ]
    EMBEDDING_FALLBACK_CHAIN: list[str] = [
        "gemini-embedding-2",
        "gemini-embedding-001",
        "text-embedding-004",
    ]
    FERNET_KEY: str
    JWT_SECRET_KEY: str
    MEDISKYE_API_KEY: str = ""
    # Comma-separated list of allowed origins. In production, set this to your
    # Cloudflare Pages URL via the ALLOWED_ORIGINS env var on Hugging Face Spaces.
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    # Native WebView origins for Android (Capacitor) and Windows Desktop (Tauri v2)
    NATIVE_APP_ORIGINS: list[str] = [
        "https://localhost",
        "http://localhost",
        "capacitor://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ]
    ALLOWED_ORIGIN_REGEX: str = r"^https://([a-z0-9-]+\.)?mediskye\.pages\.dev$"
    SHOW_SPECIALIST_CONTACTS: bool = False

    # Vertex AI / Google Cloud credentials
    GOOGLE_CLOUD_PROJECT: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT", "mediskye-backend"))
    )
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_GENAI_USE_ENTERPRISE: bool = False

    # Vector Index & Cloud Storage Persistence
    GCS_INDEX_BUCKET: str | None = None
    INDEX_STORAGE_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("INDEX_STORAGE_DIR", str(Path(tempfile.gettempdir()) / "mediskye_indexes")))
    )

    # File Upload Limits
    MEDISKYE_MAX_UPLOAD_MB: int = 50
    MAX_PDF_PAGES: int = 100
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png", ".webp"]

    # Rate Limits
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_QUERY: str = "30/minute"
    RATE_LIMIT_METRICS: str = "30/minute"
    RATE_LIMIT_SUMMARY: str = "30/minute"

    # Patient Memory & Personalization Flags
    PATIENT_MEMORY_ENABLED: bool = True
    PATIENT_MEMORY_MAX_FACTS: int = 25
    PATIENT_MEMORY_PAST_CHUNKS: int = 5
    PATIENT_MEMORY_MIN_CONFIDENCE: float = 0.6

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    VECTOR_CACHE_DIR: Path = BASE_DIR / ".vector_cache"

    @property
    def resolved_embedding_model(self) -> str:
        model = self.EMBEDDING_MODEL
        if self.GOOGLE_GENAI_USE_ENTERPRISE and model.startswith("models/"):
            return model.removeprefix("models/")
        return model

    @property
    def resolved_fallback_models(self) -> list[str]:
        models = self.GEMINI_FALLBACK_MODELS or self.MODEL_FALLBACK_CHAIN
        if self.GOOGLE_GENAI_USE_ENTERPRISE:
            return [m.removeprefix("models/") for m in models]
        return list(models)

    @property
    def resolved_embedding_fallbacks(self) -> list[str]:
        models = self.EMBEDDING_FALLBACK_CHAIN
        if self.GOOGLE_GENAI_USE_ENTERPRISE:
            return [m.removeprefix("models/") for m in models]
        return list(models)


    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value):
        """Parse ALLOWED_ORIGINS from a comma-separated (or JSON-array) env string."""
        if value is None:
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(v).strip() for v in parsed if str(v).strip()]
                except json.JSONDecodeError:
                    # Fall back to comma-separated parsing below
                    parsed = None
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("GOOGLE_CLOUD_LOCATION", mode="before")
    @classmethod
    def _normalize_location(cls, value):
        if not value or str(value).strip().lower() in ("global", "none"):
            return "asia-southeast1"
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value):
        if not value:
            return value
        return normalize_async_database_url(value)


settings = Settings()
if not settings.GOOGLE_API_KEY:
    settings.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")


settings.VECTOR_CACHE_DIR.mkdir(exist_ok=True)
