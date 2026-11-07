from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lender_policy import LenderPolicy
    from app.models.match_run import MatchRun
    from app.models.offer import Offer


class LenderDecision(Base):
    """Lender decision record storing individual policy evaluation outcomes per match run."""

    __tablename__ = "lender_decisions"

    __table_args__ = (
        UniqueConstraint(
            "match_run_id",
            "lender_policy_id",
            name="uq_lender_decisions_match_run_policy",
        ),
        CheckConstraint(
            "decision_status IN ('eligible', 'ineligible')",
            name="decision_status",
        ),
        CheckConstraint(
            "((decision_status = 'eligible' AND exclusion_reason_code IS NULL) OR "
            "(decision_status = 'ineligible' AND exclusion_reason_code IS NOT NULL))",
            name="decision_exclusion_rules",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign keys
    match_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("match_runs.id"),
        nullable=False,
        index=True,
    )
    lender_policy_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("lender_policies.id"),
        nullable=False,
        index=True,
    )

    # Immutable snapshot of the exact policy version evaluated
    policy_version_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)

    # Decision outcome and structured exclusion details
    decision_status: Mapped[str] = mapped_column(String(50), nullable=False)
    exclusion_reason_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Evaluation timestamp (timezone-aware)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    match_run: Mapped["MatchRun"] = relationship(
        "MatchRun",
        back_populates="decisions",
    )
    lender_policy: Mapped["LenderPolicy"] = relationship(
        "LenderPolicy",
        back_populates="decisions",
    )
    offer: Mapped[Optional["Offer"]] = relationship(
        "Offer",
        back_populates="lender_decision",
        uselist=False,
    )
