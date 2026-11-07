from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.consent import Consent
    from app.models.lender_decision import LenderDecision
    from app.models.loan_application import LoanApplication


class MatchRun(Base):
    """Historical matching run entity evaluating an application against lender policies."""

    __tablename__ = "match_runs"

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "run_number",
            name="uq_match_runs_application_id_run_number",
        ),
        CheckConstraint(
            "status IN ('started', 'completed', 'failed')",
            name="status",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign keys
    application_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("loan_applications.id"),
        nullable=False,
        index=True,
    )
    consent_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("consents.id"),
        nullable=False,
        index=True,
    )

    # Incremental run number per application
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="started", nullable=False)

    # Timestamps (timezone-aware)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    application: Mapped["LoanApplication"] = relationship(
        "LoanApplication",
        back_populates="match_runs",
    )
    consent: Mapped["Consent"] = relationship(
        "Consent",
        back_populates="match_runs",
    )
    # Historical decisions: preserve records without destructive delete cascade
    decisions: Mapped[List["LenderDecision"]] = relationship(
        "LenderDecision",
        back_populates="match_run",
    )
