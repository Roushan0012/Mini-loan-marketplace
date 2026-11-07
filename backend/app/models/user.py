from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead_assignment import LeadAssignment
    from app.models.loan_application import LoanApplication


class User(Base):
    """User account entity representing customers, callers, and administrators."""

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('customer', 'caller', 'admin')",
            name="role",
        ),
    )

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # User profile attributes
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Secure password hash storage (Argon2); plaintext passwords must never be persisted
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

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
    # Callers: leads assigned to this caller
    assigned_leads: Mapped[List["LeadAssignment"]] = relationship(
        "LeadAssignment",
        back_populates="caller",
    )

    # Customers: loan applications initiated by this customer
    loan_applications: Mapped[List["LoanApplication"]] = relationship(
        "LoanApplication",
        back_populates="customer",
    )
