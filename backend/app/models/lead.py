from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead_assignment import LeadAssignment
    from app.models.loan_application import LoanApplication


class Lead(Base):
    """Lead entity representing fictional training applicant records for caller workflows."""

    __tablename__ = "leads"

    __table_args__ = (
        CheckConstraint("age > 0", name="age_positive"),
        CheckConstraint("monthly_income >= 0", name="monthly_income_non_negative"),
        CheckConstraint("requested_amount > 0", name="requested_amount_positive"),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Synthetic reference code ensuring uniqueness across fictional leads
    synthetic_reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    applicant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    work_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)

    # Audit timestamp (timezone-aware)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    # Assignment to an agent/caller (1-to-1 in current simplified architecture)
    assignment: Mapped[Optional["LeadAssignment"]] = relationship(
        "LeadAssignment",
        back_populates="lead",
        uselist=False,
    )

    # Loan applications linked to or converted from this lead
    loan_applications: Mapped[List["LoanApplication"]] = relationship(
        "LoanApplication",
        back_populates="lead",
    )
