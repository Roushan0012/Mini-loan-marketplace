from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.applications import router as application_router
from app.api.v1.auth import router as auth_router
from app.api.v1.caller import router as caller_router
from app.api.v1.consents import (
    application_consents_router,
    consents_notices_router,
)
from app.api.v1.health import router as health_router
from app.api.v1.matching import router as matching_router
from app.api.v1.offers import router as offers_router
from app.api.v1.submissions import router as submissions_router
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(caller_router, prefix="/caller", tags=["caller"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(application_router, prefix="/applications", tags=["applications"])
api_router.include_router(consents_notices_router, prefix="/consents", tags=["consents"])
api_router.include_router(application_consents_router, prefix="/applications", tags=["consents"])
api_router.include_router(matching_router, prefix="/applications", tags=["matching"])
api_router.include_router(offers_router, prefix="/applications", tags=["offers"])
api_router.include_router(submissions_router, prefix="/applications", tags=["submissions"])
api_router.include_router(webhooks_router, prefix="/webhooks/mock-lenders", tags=["webhooks"])
