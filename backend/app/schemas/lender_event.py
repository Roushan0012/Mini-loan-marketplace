from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class MockLenderWebhookEvent(BaseModel):
    """Pydantic v2 schema for incoming mock lender webhook events."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1, max_length=150)
    submission_id: StrictInt = Field(..., gt=0)
    mock_reference: str = Field(..., min_length=1, max_length=150)
    lender_code: str = Field(..., min_length=1, max_length=100)
    event_type: Literal[
        "lender.accepted",
        "lender.declined",
        "lender.timed_out",
        "lender.failed",
    ]
    sequence_number: StrictInt = Field(..., gt=0)
    occurred_at: datetime
    reason_code: Optional[str] = Field(None, max_length=100)

    @field_validator("submission_id", "sequence_number", mode="before")
    @classmethod
    def reject_bool_and_non_int(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError("Boolean values are not permitted for integer fields.")
        return v

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("event_id cannot be blank or whitespace-only.")
        if len(trimmed) > 150:
            raise ValueError("event_id cannot exceed 150 characters.")
        return trimmed

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("occurred_at must be a timezone-aware datetime.")
        return v

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if len(trimmed) > 100:
                raise ValueError("reason_code cannot exceed 100 characters.")
            return trimmed if trimmed else None
        return None


class LenderEventResponse(BaseModel):
    """Pydantic v2 response returned upon webhook ingestion and processing."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    submission_id: int
    event_type: str
    sequence_number: Optional[int] = None
    processing_status: str
    submission_status: Optional[str] = None
    application_status: Optional[str] = None
    duplicate: bool
    received_at: datetime


class LenderEventHistoryItemResponse(BaseModel):
    """Pydantic v2 response item for customer-facing event history queries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    event_type: str
    sequence_number: Optional[int] = None
    processing_status: str
    occurred_at: datetime
    received_at: datetime
    event_payload: Dict[str, Any]
