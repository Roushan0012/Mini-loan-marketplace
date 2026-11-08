from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lender_decision import LenderDecision


class LenderPolicy(Base):
    """Lender underwriting policy entity storing versioned eligibility rules in JSONB.

    Supports multiple historical policy versions per lender (e.g., APEX_FINANCIAL,
    HORIZON_CREDIT, STERLING_LOANS).
    """

    __tablename__ = "lender_policies"

    __table_args__ = (
        UniqueConstraint(
            "lender_code",
            "policy_version",
            name="uq_lender_policies_lender_code_policy_version",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Lender identifiers and version metadata
    lender_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Structured mock eligibility criteria (e.g. min_age, min_monthly_income, allowed_work_types)
    rules: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Versioned mock credit terms (e.g. apr_percent, term_months, max_loan_amount)
    offer_terms: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Status and audit timestamps
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    decisions: Mapped[List["LenderDecision"]] = relationship(
        "LenderDecision",
        back_populates="lender_policy",
    )
