from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_customer
from app.db.session import get_db
from app.models.user import User
from app.schemas.offer import OfferGenerationResponse, OfferResponse
from app.services.offer_service import (
    ApplicationNotFoundError,
    OfferConfigurationError,
    OfferConsentConflictError,
    OfferMatchRunConflictError,
    OfferStatusConflictError,
    generate_application_offers,
    list_application_offers,
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
