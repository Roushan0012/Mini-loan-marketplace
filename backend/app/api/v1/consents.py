from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.permissions import require_customer
from app.db.session import get_db
from app.models.consent import Consent
from app.models.user import User
from app.schemas.consent import (
    ConsentGrantRequest,
    ConsentNoticeResponse,
    ConsentResponse,
)
from app.services.consent_notices import get_current_notices
from app.services.consent_service import (
    ConsentConflictError,
    ConsentValidationError,
    grant_application_consent,
    list_application_consents,
    revoke_application_consent,
)

# Router for published consent notices
consents_notices_router = APIRouter()

# Router for application-specific consent audit actions
application_consents_router = APIRouter()


@consents_notices_router.get(
    "/notices",
    response_model=List[ConsentNoticeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get currently published consent notices",
)
def get_published_consent_notices(
    current_user: User = Depends(require_customer),
) -> List[ConsentNoticeResponse]:
    """Retrieve the version-controlled published notices for all supported consent purposes."""
    notices = get_current_notices()
    return [ConsentNoticeResponse.model_validate(n) for n in notices]


@application_consents_router.post(
    "/{application_id}/consents",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant purpose-specific consent for a loan application",
)
def grant_consent_for_application(
    application_id: int,
    payload: ConsentGrantRequest,
    response: Response,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> Consent:
    """Grant customer consent for a loan application.

    Returns HTTP 201 for a new consent grant.
    Returns HTTP 200 for an idempotent repeat of an existing active grant.
    Returns HTTP 404 if the application is missing or not owned by current customer.
    Returns HTTP 409 if application is closed or if this version was previously revoked.
    Returns HTTP 422 if purpose or version is invalid.
    """
    try:
        consent, is_new = grant_application_consent(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
            purpose=payload.purpose,
            notice_version=payload.notice_version,
            accepted=payload.accepted,
        )
        if consent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan application not found.",
            )
        if not is_new:
            response.status_code = status.HTTP_200_OK
        return consent
    except ConsentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConsentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@application_consents_router.get(
    "/{application_id}/consents",
    response_model=List[ConsentResponse],
    status_code=status.HTTP_200_OK,
    summary="List consent history for a loan application",
)
def get_application_consent_history(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> List[Consent]:
    """Retrieve full chronological consent history for an owned loan application.

    Returns HTTP 404 if the application is missing or not owned by current customer.
    """
    history = list_application_consents(
        db=db,
        customer_id=current_user.id,
        application_id=application_id,
    )
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
    return history


@application_consents_router.post(
    "/{application_id}/consents/{consent_id}/revoke",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke a previously granted consent record",
)
def revoke_consent_for_application(
    application_id: int,
    consent_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> Consent:
    """Revoke an active consent for an owned loan application.

    Returns HTTP 200 on successful or idempotent revocation.
    Returns HTTP 404 if the application or consent record is not found or not owned.
    Returns HTTP 409 if application is closed or if consent is in an invalid transition state.
    """
    try:
        revoked_consent = revoke_application_consent(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
            consent_id=consent_id,
        )
        if revoked_consent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consent record or loan application not found.",
            )
        return revoked_consent
    except ConsentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
