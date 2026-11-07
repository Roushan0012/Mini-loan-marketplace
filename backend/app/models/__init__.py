"""SQLAlchemy model registry for Mini Loan Marketplace.

Importing all models here ensures that their table definitions and relationships
are registered with Base.metadata without circular dependencies.
"""

from app.models.consent import Consent
from app.models.lead import Lead
from app.models.lead_assignment import LeadAssignment
from app.models.loan_application import LoanApplication
from app.models.user import User

__all__ = [
    "User",
    "Lead",
    "LeadAssignment",
    "LoanApplication",
    "Consent",
]
