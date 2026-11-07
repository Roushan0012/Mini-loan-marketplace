from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.loan_application import LoanApplication


class Consent(Base):
    """Consent audit record capturing purpose-specific customer consent.

    Guarantees that active consent is recorded and auditable per application,
    purpose, and notice version before mock lender policy matching.
    """

    __tablename__ = "consents"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'granted', 'revoked')",
            name="status",
        ),
        UniqueConstraint(
            "application_id",
            "purpose",
            "notice_version",
            name="uq_consents_application_purpose_version",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign key referencing parent loan application
    application_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("loan_applications.id"),
        nullable=False,
        index=True,
    )

    # Purpose and notice version tracking
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    notice_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # State transition timestamps (timezone-aware)
    granted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    application: Mapped["LoanApplication"] = relationship(
        "LoanApplication",
        back_populates="consents",
    )
