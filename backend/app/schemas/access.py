from datetime import datetime
from decimal import Decimal
from typing import Dict

from pydantic import BaseModel, ConfigDict


class CallerLeadResponse(BaseModel):
    """Lead representation returned to an assigned caller."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    synthetic_reference: str
    applicant_name: str
    age: int
    monthly_income: Decimal
    work_type: str
    requested_amount: Decimal
    status: str
    assigned_at: datetime


class AdminDashboardSummary(BaseModel):
    """Aggregate metrics and pipeline counts for administrator monitoring."""

    total_leads: int
    total_applications: int
    total_match_runs: int
    total_offers: int
    total_submissions: int
    applications_by_status: Dict[str, int]
    lender_events_by_processing_status: Dict[str, int]
