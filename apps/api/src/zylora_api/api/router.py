from fastapi import APIRouter

from zylora_api.api.admin_auth import router as admin_auth_router
from zylora_api.api.auth import router as auth_router
from zylora_api.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_auth_router)
