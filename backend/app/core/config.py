import os
import json
from pathlib import Path
from typing import Annotated, List, Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

# Load root .env file if available
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    PROJECT_NAME: str = "MediSkye AI Medical Assistant"
    VERSION: str = "2.0.0"
    API_V1_STR: str = ""

    # Environment
    ENV: str = "production"
    DEBUG: bool = False

    # Database & Redis
    DATABASE_URL: str = "sqlite+aiosqlite:///./mediskye.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security & API Key
    GOOGLE_API_KEY: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    GEMINI_MODEL: str = "gemini-3.8-flash"
    EMBEDDING_MODEL: str = "models/gemini-embedding-2"
    GEMINI_FALLBACK_MODELS: List[str] = [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ]
    FERNET_KEY: str
    JWT_SECRET_KEY: str
    MEDISKYE_API_KEY: str = ""
    # Comma-separated list of allowed origins. In production, set this to your
    # Cloudflare Pages URL via the ALLOWED_ORIGINS env var on Hugging Face Spaces.
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    SHOW_SPECIALIST_CONTACTS: bool = False

    # Vertex AI / Google Cloud credentials
    GOOGLE_CLOUD_PROJECT: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT", "mediskye-backend"))
    )
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_GENAI_USE_ENTERPRISE: bool = False

    # Vector Index & Cloud Storage Persistence
    GCS_INDEX_BUCKET: Optional[str] = None
    INDEX_STORAGE_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("INDEX_STORAGE_DIR", str(Path(__file__).resolve().parent.parent.parent / "indexes")))
    )

    # File Upload Limits
    MEDISKYE_MAX_UPLOAD_MB: int = 50
    MAX_PDF_PAGES: int = 100
    ALLOWED_MIME_TYPES: List[str] = ["application/pdf"]
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".jpg", ".jpeg", ".png"]

    # Rate Limits
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_QUERY: str = "30/minute"

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
    def resolved_fallback_models(self) -> List[str]:
        models = self.GEMINI_FALLBACK_MODELS
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
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value


settings = Settings()
if not settings.GOOGLE_API_KEY:
    settings.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")


settings.VECTOR_CACHE_DIR.mkdir(exist_ok=True)
