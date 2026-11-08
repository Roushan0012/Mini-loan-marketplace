from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.consent_notices import SUPPORTED_PURPOSES


class ConsentNoticeResponse(BaseModel):
    """Public representation of a published consent notice."""

    model_config = ConfigDict(from_attributes=True)

    purpose: str
    title: str
    notice_version: str
    notice_text: str
    required_for_matching: bool


class ConsentGrantRequest(BaseModel):
    """Payload to grant demo consent for a specific purpose and notice version."""

    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(..., description="Consent purpose identifier")
    notice_version: str = Field(..., min_length=1, max_length=50, description="Notice version")
    accepted: bool = Field(..., description="Customer agreement flag; must be true")

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        norm = (v or "").strip().lower()
        if norm not in SUPPORTED_PURPOSES:
            raise ValueError(f"Invalid consent purpose. Supported purposes: {sorted(SUPPORTED_PURPOSES)}")
        return norm

    @field_validator("accepted")
    @classmethod
    def validate_accepted(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Consent must be accepted (accepted=true) to grant consent.")
        return v


class ConsentResponse(BaseModel):
    """Audit record response for a granted or revoked customer consent."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    purpose: str
    notice_version: str
    status: str
    granted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
