from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lender_event import LenderEvent
    from app.models.loan_application import LoanApplication
    from app.models.offer import Offer


class OfferSubmission(Base):
    """Offer submission record representing a customer's final commitment to an offer."""

    __tablename__ = "offer_submissions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'submitted', 'accepted', 'declined', 'timed_out', 'failed')",
            name="status",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Unique application foreign key: enforces at most one selected offer submission per application
    application_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("loan_applications.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Unique offer foreign key: ensures an offer is not submitted more than once
    offer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("offers.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Unique client/backend idempotency key preventing duplicate dispatch requests
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    # Submission lifecycle status
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Mock provider reference returned upon submission
    mock_reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # Timestamps (timezone-aware)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
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
    application: Mapped["LoanApplication"] = relationship(
        "LoanApplication",
        back_populates="offer_submissions",
    )
    offer: Mapped["Offer"] = relationship(
        "Offer",
        back_populates="submission",
    )
    # Event ledger: retain audit history without destructive delete cascade
    events: Mapped[List["LenderEvent"]] = relationship(
        "LenderEvent",
        back_populates="submission",
    )
