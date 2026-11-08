from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_customer
from app.db.session import get_db
from app.models.user import User
from app.schemas.matching import MatchRunResponse, MatchRunSummaryResponse
from app.services.matching_service import (
    ApplicationNotFoundError,
    MatchingConcurrencyConflictError,
    MatchingConfigurationError,
    MatchingConsentConflictError,
    MatchingStatusConflictError,
    list_match_run_history,
    run_matching,
)

router = APIRouter()


@router.post(
    "/{application_id}/match",
    response_model=MatchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute multi-lender eligibility matching",
)
def match_loan_application(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> MatchRunResponse:
    """Execute deterministic multi-lender eligibility matching for an owned loan application.

    Enforces:
    - Customer authentication and application ownership.
    - Application status check ('draft' or 'matched').
    - Verification of active granted consent for all required notice purposes.
    - Returns HTTP 201 with full MatchRunResponse and evaluated decisions.
    """
    try:
        match_run = run_matching(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
        )
        return MatchRunResponse.model_validate(match_run)
    except ApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
    except (MatchingStatusConflictError, MatchingConcurrencyConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except MatchingConsentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "missing_purposes": exc.missing_purposes,
            },
        )
    except MatchingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.get(
    "/{application_id}/matches",
    response_model=MatchRunSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve chronological matching history",
)
def get_loan_application_matches(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> MatchRunSummaryResponse:
    """Retrieve full chronological match run history and decisions for an owned loan application."""
    try:
        return list_match_run_history(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
        )
    except ApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
