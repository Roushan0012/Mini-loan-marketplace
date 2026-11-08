from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.webhook_security import verify_mock_webhook_signature
from app.db.session import get_db
from app.schemas.lender_event import LenderEventResponse, MockLenderWebhookEvent
from app.services.lender_event_service import (
    LenderEventConfigurationError,
    LenderEventConflictError,
    SubmissionNotFoundError,
    process_mock_lender_event,
)

router = APIRouter()


@router.post(
    "/events",
    response_model=LenderEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive and process mock lender webhook events",
)
async def receive_mock_lender_event(
    request: Request,
    db: Session = Depends(get_db),
) -> LenderEventResponse:
    """Receive, authenticate via HMAC-SHA256, and process asynchronous mock lender events.

    Enforces:
    - Verifies MOCK_LENDER_WEBHOOK_SECRET is configured; returns 503 if missing.
    - Validates HMAC-SHA256 signature in X-Mock-Lender-Signature over raw request bytes; returns 401 if invalid.
    - Validates strict event schema; returns 422 if malformed or containing unpermitted fields.
    - Idempotent duplicate event handling and sequence-number ordering.
    - Returns HTTP 200 with LenderEventResponse.
    - Returns HTTP 404 if submission is unknown or mock reference / lender code mismatches.
    - Returns HTTP 409 if event_id is reused with conflicting content or invalid state.
    """
    # 1. Check if webhook signing secret is configured
    secret = settings.MOCK_LENDER_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mock lender webhook signing secret is not configured.",
        )

    # 2. Read raw request bytes and signature header
    raw_body = await request.body()
    signature = request.headers.get("X-Mock-Lender-Signature")

    # 3. Verify HMAC-SHA256 signature
    if not verify_mock_webhook_signature(raw_body, signature, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature.",
        )

    # 4. Parse and validate JSON schema
    try:
        event = MockLenderWebhookEvent.model_validate_json(raw_body)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # 5. Process event
    try:
        return process_mock_lender_event(db=db, event=event)
    except SubmissionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except LenderEventConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except LenderEventConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
