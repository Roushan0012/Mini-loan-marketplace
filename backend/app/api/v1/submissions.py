from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_customer
from app.db.session import get_db
from app.models.user import User
from app.schemas.offer import OfferSubmissionResponse
from app.services.submission_service import (
    SubmissionAdapterError,
    SubmissionApplicationNotFoundError,
    SubmissionConflictError,
    SubmissionConsentConflictError,
    SubmissionOfferNotFoundError,
    submit_selected_offer,
)

router = APIRouter()


@router.post(
    "/{application_id}/offers/{offer_id}/submit",
    response_model=OfferSubmissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit selected loan offer to mock lender",
)
def submit_offer_endpoint(
    application_id: int,
    offer_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> OfferSubmissionResponse:
    """Submit a customer's selected loan offer to a fictional mock lender idempotently.

    Enforces:
    - Customer authentication and loan application ownership.
    - Required 'Idempotency-Key' HTTP header (8-128 characters).
    - Application status check ('offer_selected').
    - Selected offer status check ('selected') and eligible lender decision.
    - Active mandatory consents re-verification (bypassed on exact idempotent replay).
    - Deterministic local mock adapter dispatch with non-PII receipt generation.
    - Returns HTTP 200 with OfferSubmissionResponse on initial creation and replay.
    - Returns HTTP 404 if application or offer not found / not owned.
    - Returns HTTP 409 for conflicts (lifecycle status, idempotency mismatch, consent missing).
    - Returns HTTP 503 for mock adapter errors.
    """
    if idempotency_key is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required header: 'Idempotency-Key'.",
        )

    trimmed_key = idempotency_key.strip()
    if not trimmed_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Header 'Idempotency-Key' cannot be blank or whitespace-only.",
        )

    if len(trimmed_key) < 8 or len(trimmed_key) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Header 'Idempotency-Key' length must be between 8 and 128 characters.",
        )

    try:
        return submit_selected_offer(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
            offer_id=offer_id,
            idempotency_key=trimmed_key,
        )
    except SubmissionApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
    except SubmissionOfferNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found.",
        )
    except SubmissionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except SubmissionConsentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "missing_purposes": exc.missing_purposes,
            },
        )
    except SubmissionAdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
