from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def get_health() -> dict[str, str]:
    """Health check endpoint returning service status."""
    return {
        "status": "ok",
        "service": "mini-loan-marketplace-api",
    }
