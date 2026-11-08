from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.applications import router as application_router
from app.api.v1.auth import router as auth_router
from app.api.v1.caller import router as caller_router
from app.api.v1.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(caller_router, prefix="/caller", tags=["caller"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(application_router, prefix="/applications", tags=["applications"])
