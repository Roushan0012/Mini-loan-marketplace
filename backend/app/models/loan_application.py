from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.consent import Consent
    from app.models.lead import Lead
    from app.models.match_run import MatchRun
    from app.models.offer_submission import OfferSubmission
    from app.models.user import User


class LoanApplication(Base):
    """Loan application entity tracking customer credit inquiry lifecycle and parameters."""

    __tablename__ = "loan_applications"

    __table_args__ = (
        CheckConstraint("age > 0", name="age_positive"),
        CheckConstraint(
            "monthly_income >= 0",
            name="monthly_income_non_negative",
        ),
        CheckConstraint(
            "requested_amount > 0",
            name="requested_amount_positive",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign key referencing customer user
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Optional foreign key referencing origin lead
    lead_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("leads.id"),
        nullable=True,
        index=True,
    )

    # Core applicant input parameters
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    work_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    # Audit timestamps (timezone-aware)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    customer: Mapped["User"] = relationship(
        "User",
        back_populates="loan_applications",
    )
    lead: Mapped[Optional["Lead"]] = relationship(
        "Lead",
        back_populates="loan_applications",
    )
    consents: Mapped[List["Consent"]] = relationship(
        "Consent",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    match_runs: Mapped[List["MatchRun"]] = relationship(
        "MatchRun",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    offer_submissions: Mapped[List["OfferSubmission"]] = relationship(
        "OfferSubmission",
        back_populates="application",
        cascade="all, delete-orphan",
    )
