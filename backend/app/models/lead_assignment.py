from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.user import User


class LeadAssignment(Base):
    """Lead assignment record associating a mock lead to an assigned caller.

    The unique constraint on lead_id ensures one current caller assignment per lead.
    """

    __tablename__ = "lead_assignments"

    # BigInteger primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign keys: unique lead_id guarantees single assignment
    lead_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("leads.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    caller_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Timestamp when lead was assigned
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    lead: Mapped["Lead"] = relationship(
        "Lead",
        back_populates="assignment",
    )
    caller: Mapped["User"] = relationship(
        "User",
        back_populates="assigned_leads",
    )
