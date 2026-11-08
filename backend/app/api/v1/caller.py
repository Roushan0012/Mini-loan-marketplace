from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_caller
from app.db.session import get_db
from app.models.lead import Lead
from app.models.lead_assignment import LeadAssignment
from app.models.user import User
from app.schemas.access import CallerLeadResponse

router = APIRouter()


@router.get(
    "/leads",
    response_model=List[CallerLeadResponse],
    status_code=status.HTTP_200_OK,
    summary="List mock leads assigned to the authenticated caller",
)
def get_caller_leads(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of leads to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(require_caller),
    db: Session = Depends(get_db),
) -> List[CallerLeadResponse]:
    """Retrieve leads assigned exclusively to the authenticated caller.

    Enforces:
    - Caller role check via require_caller.
    - Automatic caller scoping using current_user.id (never trusted from request parameters).
    - Stable ordering by Lead.id.
    - Basic pagination via limit and offset.
    - Empty list returned when no leads are assigned.
    """
    rows = (
        db.query(
            Lead.id,
            Lead.synthetic_reference,
            Lead.applicant_name,
            Lead.age,
            Lead.monthly_income,
            Lead.work_type,
            Lead.requested_amount,
            Lead.status,
            LeadAssignment.assigned_at,
        )
        .join(LeadAssignment, Lead.id == LeadAssignment.lead_id)
        .filter(LeadAssignment.caller_id == current_user.id)
        .order_by(Lead.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        CallerLeadResponse(
            id=row.id,
            synthetic_reference=row.synthetic_reference,
            applicant_name=row.applicant_name,
            age=row.age,
            monthly_income=row.monthly_income,
            work_type=row.work_type,
            requested_amount=row.requested_amount,
            status=row.status,
            assigned_at=row.assigned_at,
        )
        for row in rows
    ]
