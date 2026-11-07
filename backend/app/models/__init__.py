"""SQLAlchemy model registry for Mini Loan Marketplace.

Importing all eleven models here ensures that their table definitions, constraints,
and relationships are registered with Base.metadata without circular dependencies.
"""

from app.models.consent import Consent
from app.models.lead import Lead
from app.models.lead_assignment import LeadAssignment
from app.models.lender_decision import LenderDecision
from app.models.lender_event import LenderEvent
from app.models.lender_policy import LenderPolicy
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from app.models.user import User

__all__ = [
    "User",
    "Lead",
    "LeadAssignment",
    "LoanApplication",
    "Consent",
    "LenderPolicy",
    "MatchRun",
    "LenderDecision",
    "Offer",
    "OfferSubmission",
    "LenderEvent",
]
