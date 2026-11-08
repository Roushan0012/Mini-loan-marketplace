from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.db.session import get_db
from app.models.lead import Lead
from app.models.lender_event import LenderEvent
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from app.models.user import User
from app.schemas.access import AdminDashboardSummary

router = APIRouter()


@router.get(
    "/dashboard/metrics",
    response_model=AdminDashboardSummary,
    status_code=status.HTTP_200_OK,
    summary="Get application funnel and integration aggregate metrics",
)
def get_dashboard_metrics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminDashboardSummary:
    """Retrieve aggregate monitoring metrics for the administrative dashboard.

    Computes counts and status groupings directly in PostgreSQL using SQL aggregate
    functions (COUNT, GROUP BY). Never returns individual customer PII, loan details,
    or event payloads.
    """
    total_leads = db.query(func.count(Lead.id)).scalar() or 0
    total_applications = db.query(func.count(LoanApplication.id)).scalar() or 0
    total_match_runs = db.query(func.count(MatchRun.id)).scalar() or 0
    total_offers = db.query(func.count(Offer.id)).scalar() or 0
    total_submissions = db.query(func.count(OfferSubmission.id)).scalar() or 0

    applications_by_status = dict(
        db.query(LoanApplication.status, func.count(LoanApplication.id))
        .group_by(LoanApplication.status)
        .all()
    )

    lender_events_by_processing_status = dict(
        db.query(LenderEvent.processing_status, func.count(LenderEvent.id))
        .group_by(LenderEvent.processing_status)
        .all()
    )

    return AdminDashboardSummary(
        total_leads=total_leads,
        total_applications=total_applications,
        total_match_runs=total_match_runs,
        total_offers=total_offers,
        total_submissions=total_submissions,
        applications_by_status=applications_by_status,
        lender_events_by_processing_status=lender_events_by_processing_status,
    )
