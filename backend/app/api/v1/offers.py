from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_customer
from app.db.session import get_db
from app.models.user import User
from app.schemas.offer import (
    MockKFSResponse,
    OfferGenerationResponse,
    OfferResponse,
    OfferSelectionResponse,
)
from app.services.offer_service import (
    ApplicationNotFoundError,
    OfferConfigurationError,
    OfferConsentConflictError,
    OfferMatchRunConflictError,
    OfferNotFoundError,
    OfferSelectionConflictError,
    OfferStatusConflictError,
    generate_application_offers,
    get_mock_kfs_details,
    list_application_offers,
    select_application_offer,
)

router = APIRouter()


@router.post(
    "/{application_id}/offers/generate",
    response_model=OfferGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate mock loan offers for eligible lender decisions",
)
def generate_offers_endpoint(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> OfferGenerationResponse:
    """Generate mock loan offers for all eligible decisions belonging to the latest completed match run.

    Enforces:
    - Customer authentication and loan application ownership.
    - Application status check ('matched').
    - Verification of active current-version consents.
    - Presence of latest completed match run.
    - Idempotent execution (returns existing offers without duplication or term alteration).
    - Returns HTTP 200 with OfferGenerationResponse.
    """
    try:
        return generate_application_offers(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
        )
    except ApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
    except (OfferStatusConflictError, OfferMatchRunConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except OfferConsentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "missing_purposes": exc.missing_purposes,
            },
        )
    except OfferConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.get(
    "/{application_id}/offers",
    response_model=List[OfferResponse],
    status_code=status.HTTP_200_OK,
    summary="List mock loan offers for latest completed match run",
)
def list_offers_endpoint(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> List[OfferResponse]:
    """Retrieve all credit offers belonging to the latest completed match run of an owned application.

    Enforces:
    - Customer authentication and loan application ownership.
    - Scopes offers strictly to the latest completed MatchRun.
    - Returns empty list if no match run exists or latest match run is not completed.
    - Returns HTTP 200 with list of OfferResponse objects ordered by lender code.
    """
    try:
        return list_application_offers(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
        )
    except ApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )


@router.get(
    "/{application_id}/offers/{offer_id}/kfs",
    response_model=MockKFSResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve mock Key Facts Statement (KFS) disclosure for an offer",
)
def get_mock_kfs_endpoint(
    application_id: int,
    offer_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> MockKFSResponse:
    """Retrieve Key Facts Statement (KFS) details for a specific loan offer.

    Enforces:
    - Customer authentication and loan application ownership.
    - Verified relationship: Offer -> LenderDecision -> MatchRun -> LoanApplication.
    - Returns HTTP 200 with MockKFSResponse.
    - Returns HTTP 404 if application not found, not owned, or offer does not belong to application.
    - Preserves offer records without modification or duplication.
    """
    try:
        return get_mock_kfs_details(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
            offer_id=offer_id,
        )
    except ApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
    except OfferNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found.",
        )


@router.post(
    "/{application_id}/offers/{offer_id}/select",
    response_model=OfferSelectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Select a mock loan offer for an application",
)
def select_offer_endpoint(
    application_id: int,
    offer_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> OfferSelectionResponse:
    """Select exactly one available loan offer for a matched loan application.

    Enforces:
    - Customer authentication and loan application ownership.
    - Application status check ('matched' or idempotent 'offer_selected').
    - Verification of active current-version consents (for new selection).
    - Scopes selectable offer to latest completed match run with eligible decision and available status.
    - Transitions selected offer to 'selected' and application to 'offer_selected'.
    - Atomically withdraws other available offers for the application.
    - Returns HTTP 200 with OfferSelectionResponse.
    - Returns HTTP 404 if application or offer not found / not owned.
    - Returns HTTP 409 for conflicts (application status, offer status, consent, or mismatch).
    """
    try:
        return select_application_offer(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
            offer_id=offer_id,
        )
    except ApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
    except OfferNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found.",
        )
    except (
        OfferStatusConflictError,
        OfferMatchRunConflictError,
        OfferSelectionConflictError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except OfferConsentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "missing_purposes": exc.missing_purposes,
            },
        )
