from fastapi import APIRouter
from app.core.config import settings
from app.schemas.health import HealthCheckResponse

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, tags=["Health"])
@router.get("/liveness", response_model=HealthCheckResponse, tags=["Health"])
@router.get("/readiness", response_model=HealthCheckResponse, tags=["Health"])
async def get_health_status():
    return HealthCheckResponse(
        status="healthy",
        version=settings.VERSION,
        environment=settings.ENV,
    )
