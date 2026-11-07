from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

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
    from app.models.lender_decision import LenderDecision
    from app.models.offer_submission import OfferSubmission


class Offer(Base):
    """Credit offer entity generated from an eligible mock lender decision."""

    __tablename__ = "offers"

    __table_args__ = (
        CheckConstraint("loan_amount > 0", name="loan_amount_positive"),
        CheckConstraint("apr >= 0", name="apr_non_negative"),
        CheckConstraint("term_months > 0", name="term_months_positive"),
        CheckConstraint("monthly_installment > 0", name="monthly_installment_positive"),
        CheckConstraint(
            "status IN ('available', 'selected', 'expired', 'withdrawn')",
            name="status",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 1-to-1 foreign key referencing eligible lender decision
    lender_decision_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("lender_decisions.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Financial terms (monetary values as Numeric(12, 2); APR as percentage Numeric(7, 4))
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    apr: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_installment: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Mock regulatory disclosure / Key Fact Statement link
    mock_kfs_reference: Mapped[str] = mapped_column(String(255), nullable=False)

    # Offer lifecycle status
    status: Mapped[str] = mapped_column(String(50), default="available", nullable=False)

    # Audit and validity timestamps (timezone-aware)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    lender_decision: Mapped["LenderDecision"] = relationship(
        "LenderDecision",
        back_populates="offer",
    )
    submission: Mapped[Optional["OfferSubmission"]] = relationship(
        "OfferSubmission",
        back_populates="offer",
        uselist=False,
    )
