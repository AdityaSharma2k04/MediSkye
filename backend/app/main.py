import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.limiter import limiter

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.middleware.error_handler import global_exception_handler, http_exception_handler
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.body_limit import BodySizeLimitMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.observability import init_sentry
init_sentry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Lifespan
    COMPROMISED_FERNET_KEY = "UAgBIptmb50gZM94VLBKia38mASQ4w-5H6KCS_z7_YM="
    if not settings.FERNET_KEY:
        raise RuntimeError(
            "FERNET_KEY environment variable is required. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if settings.FERNET_KEY == COMPROMISED_FERNET_KEY:
        raise RuntimeError(
            "FERNET_KEY is set to the compromised key that was hardcoded in source. "
            "Generate a new one and update .env before starting the app."
        )
    if not settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set and at least 32 characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENV}]")

    if settings.GOOGLE_GENAI_USE_ENTERPRISE:
        logger.info(
            "Vertex AI enterprise mode enabled via Cloud Run ADC (project=%s, location=%s)",
            settings.GOOGLE_CLOUD_PROJECT,
            settings.GOOGLE_CLOUD_LOCATION,
        )
    else:
        logger.info("Gemini API Key mode active (enterprise mode disabled).")

    import firebase_admin

    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app(options={"projectId": settings.GOOGLE_CLOUD_PROJECT or "mediskye-backend"})
            logger.info("Firebase Admin initialized successfully.")
        except Exception:
            try:
                firebase_admin.initialize_app()
                logger.info("Firebase Admin initialized successfully via ADC.")
            except Exception as fb_err:
                logger.warning("Firebase Admin initialization deferred/failed: %s", fb_err)

    # DEV ONLY: auto-create tables for SQLite convenience
    # In production, Alembic migrations are the source of truth
    import app.db.models
    from app.db.database import engine, Base
    async with engine.begin() as conn:
        if settings.ENV == "development":
            await conn.run_sync(Base.metadata.create_all)

        def _ensure_document_cache_columns(sync_conn):
            from sqlalchemy import inspect, text
            inspector = inspect(sync_conn)
            if "documents" in inspector.get_table_names():
                existing_cols = {c["name"] for c in inspector.get_columns("documents")}
                dialect = sync_conn.dialect.name
                if "cached_metrics" not in existing_cols:
                    if dialect == "postgresql":
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS cached_metrics JSON"))
                    else:
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN cached_metrics JSON"))
                if "cached_summary" not in existing_cols:
                    if dialect == "postgresql":
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS cached_summary TEXT"))
                    else:
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN cached_summary TEXT"))
                if "index_status" not in existing_cols:
                    if dialect == "postgresql":
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS index_status VARCHAR(20) DEFAULT 'building' NOT NULL"))
                    else:
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN index_status VARCHAR(20) DEFAULT 'building' NOT NULL"))

            if "chats" in inspector.get_table_names():
                existing_chat_cols = {c["name"] for c in inspector.get_columns("chats")}
                if "dependent_id" not in existing_chat_cols:
                    if dialect == "postgresql":
                        sync_conn.execute(text("ALTER TABLE chats ADD COLUMN IF NOT EXISTS dependent_id UUID REFERENCES dependent_profiles(id) ON DELETE CASCADE"))
                        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chats_dependent_id ON chats(dependent_id)"))
                    else:
                        sync_conn.execute(text("ALTER TABLE chats ADD COLUMN dependent_id CHAR(32)"))
                        sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chats_dependent_id ON chats(dependent_id)"))

        await conn.run_sync(_ensure_document_cache_columns)

    try:
        from app.services.upload_jobs import fail_stale_building_documents
        swept = await fail_stale_building_documents()
        if swept:
            logger.warning("Marked %d stale 'building' document(s) as failed on startup", swept)
    except Exception as sweep_err:
        logger.warning("Startup stale-document sweep skipped: %s", sweep_err)

    yield
    
    # Shutdown Lifespan
    logger.info("Shutting down MediSkye AI backend gracefully.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Process Time Middleware (X-Process-Time-Ms)
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    return response

# Rate Limiter Configuration
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Exception Handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Custom Middlewares
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)

# CORS Configuration with Amortized Preflight Max-Age
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
    expose_headers=["*", "X-Process-Time-Ms"],
)

# API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Static Files Mount for Frontend
frontend_path = settings.BASE_DIR.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path), html=True), name="static")
