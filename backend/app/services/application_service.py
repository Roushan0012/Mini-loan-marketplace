from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.loan_application import LoanApplication


class NonDraftApplicationError(ValueError):
    """Raised when modifying an application that is no longer in draft status."""

    pass


def create_application(
    db: Session,
    customer_id: int,
    age: int,
    monthly_income: Decimal,
    work_type: str,
    requested_amount: Decimal,
) -> LoanApplication:
    """Create a new loan application in draft status for the authenticated customer.

    Enforces:
    - customer_id derived exclusively from the authenticated user.
    - status initialized to 'draft' on the backend.
    - lead_id unassociated.
    - Transaction rollback on database errors.
    """
    application = LoanApplication(
        customer_id=customer_id,
        age=age,
        monthly_income=monthly_income,
        work_type=work_type,
        requested_amount=requested_amount,
        status="draft",
        lead_id=None,
    )
    db.add(application)
    try:
        db.commit()
        db.refresh(application)
        return application
    except Exception:
        db.rollback()
        raise


def list_customer_applications(
    db: Session,
    customer_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[LoanApplication]:
    """Retrieve loan applications owned exclusively by the authenticated customer.

    Ordered newest first by created_at and id descending, with pagination support.
    """
    return (
        db.query(LoanApplication)
        .filter(LoanApplication.customer_id == customer_id)
        .order_by(LoanApplication.created_at.desc(), LoanApplication.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_customer_application(
    db: Session,
    customer_id: int,
    application_id: int,
) -> Optional[LoanApplication]:
    """Retrieve a specific loan application only if owned by the authenticated customer.

    Returns None if the application does not exist or belongs to another customer.
    """
    return (
        db.query(LoanApplication)
        .filter(
            LoanApplication.id == application_id,
            LoanApplication.customer_id == customer_id,
        )
        .first()
    )


def update_customer_application(
    db: Session,
    customer_id: int,
    application_id: int,
    update_data: Dict[str, Any],
) -> Optional[LoanApplication]:
    """Partially update a customer's draft loan application.

    Enforces:
    - Ownership verification (application must belong to customer_id).
    - Status check (only 'draft' applications are editable).
    - Applies only supplied fields.
    - Transaction rollback on database errors.
    """
    application = get_customer_application(
        db=db,
        customer_id=customer_id,
        application_id=application_id,
    )
    if application is None:
        return None

    if application.status != "draft":
        raise NonDraftApplicationError(
            f"Application {application_id} cannot be modified because its status is '{application.status}'."
        )

    for field, value in update_data.items():
        if hasattr(application, field):
            setattr(application, field, value)

    try:
        db.commit()
        db.refresh(application)
        return application
    except Exception:
        db.rollback()
        raise
