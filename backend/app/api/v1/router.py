from fastapi import APIRouter
from app.api.v1.endpoints import health, upload, query, metrics, auth, user, chat

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(upload.router)
api_router.include_router(query.router)
api_router.include_router(metrics.router)
api_router.include_router(user.router)
api_router.include_router(chat.router)
