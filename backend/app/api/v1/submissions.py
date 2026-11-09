from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_customer
from app.db.session import get_db
from app.models.lender_event import LenderEvent
from app.models.loan_application import LoanApplication
from app.models.offer_submission import OfferSubmission
from app.models.user import User
from app.schemas.lender_event import LenderEventHistoryItemResponse
from app.schemas.offer import OfferSubmissionResponse, OfferSubmissionStatusResponse
from app.services.submission_service import (
    SubmissionAdapterError,
    SubmissionApplicationNotFoundError,
    SubmissionConflictError,
    SubmissionConsentConflictError,
    SubmissionOfferNotFoundError,
    get_application_submission_status,
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


@router.get(
    "/{application_id}/submission",
    response_model=Optional[OfferSubmissionStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current offer submission status for a loan application",
)
def get_submission_status_endpoint(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> Optional[OfferSubmissionStatusResponse]:
    """Retrieve the current submission status for a customer's loan application.

    Enforces:
    - Customer authentication and loan application ownership.
    - Returns HTTP 404 if application not found or not owned by the customer.
    - Returns HTTP 200 with JSON null if application has no submission yet.
    - Returns HTTP 200 with OfferSubmissionStatusResponse if submission exists.
    - Read-only query; does not modify records, timestamps, or statuses.
    """
    try:
        return get_application_submission_status(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
        )
    except SubmissionApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )


@router.get(
    "/{application_id}/submission/events",
    response_model=List[LenderEventHistoryItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get webhook event audit history for an application submission",
)
def get_submission_events_endpoint(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> List[LenderEventHistoryItemResponse]:
    """Retrieve all webhook events recorded for a customer's loan application submission.

    Enforces:
    - Customer authentication and loan application ownership.
    - Returns 404 if application not found or not owned by the customer.
    - Returns empty list if application has no submission yet.
    - Deterministic ordering: sequence_number ASC, occurred_at ASC, id ASC.
    - Sanitized event payload without secrets or raw customer PII.
    """
    app = (
        db.query(LoanApplication)
        .filter(
            LoanApplication.id == application_id,
            LoanApplication.customer_id == current_user.id,
        )
        .first()
    )
    if app is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )

    submission = (
        db.query(OfferSubmission)
        .filter(OfferSubmission.application_id == application_id)
        .first()
    )
    if submission is None:
        return []

    events = (
        db.query(LenderEvent)
        .filter(LenderEvent.submission_id == submission.id)
        .order_by(
            LenderEvent.sequence_number.asc().nulls_last(),
            LenderEvent.occurred_at.asc(),
            LenderEvent.id.asc(),
        )
        .all()
    )
    return [LenderEventHistoryItemResponse.model_validate(e) for e in events]
