from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.offer_submission import OfferSubmission


class LenderEvent(Base):
    """Lender event / webhook log tracking asynchronous provider callbacks.

    Enforces idempotency: repeated delivery of an existing event_id is rejected by the unique constraint.
    """

    __tablename__ = "lender_events"

    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('received', 'processed', 'ignored', 'failed')",
            name="processing_status",
        ),
        CheckConstraint(
            "sequence_number IS NULL OR sequence_number > 0",
            name="sequence_number_positive",
        ),
        Index("ix_lender_events_submission_received", "submission_id", "received_at"),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Submission foreign key
    submission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("offer_submissions.id"),
        nullable=False,
        index=True,
    )

    # Provider unique event ID ensuring idempotent webhook ingestion
    event_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    # Event taxonomy and optional sequencing
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Raw payload from external provider
    event_payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Event processing state
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="received",
        nullable=False,
    )

    # Timestamps (timezone-aware)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    submission: Mapped["OfferSubmission"] = relationship(
        "OfferSubmission",
        back_populates="events",
    )
