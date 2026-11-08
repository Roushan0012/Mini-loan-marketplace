from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_customer
from app.db.session import get_db
from app.models.loan_application import LoanApplication
from app.models.user import User
from app.schemas.application import (
    LoanApplicationCreate,
    LoanApplicationResponse,
    LoanApplicationUpdate,
)
from app.services.application_service import (
    NonDraftApplicationError,
    create_application,
    get_customer_application,
    list_customer_applications,
    update_customer_application,
)

router = APIRouter()


@router.post(
    "",
    response_model=LoanApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new draft loan application",
)
def create_loan_application(
    payload: LoanApplicationCreate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> LoanApplication:
    """Create a new loan application in 'draft' status for the authenticated customer.

    customer_id is assigned strictly from the authenticated user identity.
    """
    return create_application(
        db=db,
        customer_id=current_user.id,
        age=payload.age,
        monthly_income=payload.monthly_income,
        work_type=payload.work_type,
        requested_amount=payload.requested_amount,
    )


@router.get(
    "",
    response_model=List[LoanApplicationResponse],
    status_code=status.HTTP_200_OK,
    summary="List all loan applications for the authenticated customer",
)
def list_loan_applications(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum applications to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> List[LoanApplication]:
    """Retrieve loan applications owned by the authenticated customer.

    Ordered newest first, with pagination support. Returns an empty list if none exist.
    """
    return list_customer_applications(
        db=db,
        customer_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{application_id}",
    response_model=LoanApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a specific loan application by ID",
)
def get_single_loan_application(
    application_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> LoanApplication:
    """Retrieve an application only if owned by the authenticated customer.

    Returns HTTP 404 if the application does not exist or belongs to another user.
    """
    application = get_customer_application(
        db=db,
        customer_id=current_user.id,
        application_id=application_id,
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan application not found.",
        )
    return application


@router.patch(
    "/{application_id}",
    response_model=LoanApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a draft loan application",
)
def update_loan_application(
    application_id: int,
    payload: LoanApplicationUpdate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> LoanApplication:
    """Update fields of an application in 'draft' status.

    Returns HTTP 404 if the application is missing or not owned by current user.
    Returns HTTP 409 if the application is no longer in draft status.
    """
    update_data = payload.model_dump(exclude_unset=True)
    try:
        updated_app = update_customer_application(
            db=db,
            customer_id=current_user.id,
            application_id=application_id,
            update_data=update_data,
        )
        if updated_app is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan application not found.",
            )
        return updated_app
    except NonDraftApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
