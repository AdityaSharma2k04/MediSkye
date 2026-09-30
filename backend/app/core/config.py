import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    FERNET_KEY: str
    JWT_SECRET_KEY: str
    MEDISKYE_API_KEY: str = ""
    ALLOWED_ORIGINS: List[str] = ["*"]

    # File Upload Limits
    MEDISKYE_MAX_UPLOAD_MB: int = 50
    MAX_PDF_PAGES: int = 100
    ALLOWED_MIME_TYPES: List[str] = ["application/pdf"]
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]

    # Rate Limits
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_QUERY: str = "30/minute"

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    VECTOR_CACHE_DIR: Path = BASE_DIR / ".vector_cache"

    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
if not settings.GOOGLE_API_KEY:
    settings.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

settings.VECTOR_CACHE_DIR.mkdir(exist_ok=True)
