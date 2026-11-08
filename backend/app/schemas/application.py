from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_WORK_TYPES = {"salaried", "self_employed", "other"}


class LoanApplicationCreate(BaseModel):
    """Payload to create a new draft loan application."""

    model_config = ConfigDict(extra="forbid")

    age: int = Field(..., gt=0, le=120, description="Applicant age in years")
    monthly_income: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Applicant monthly income",
    )
    work_type: str = Field(
        ...,
        max_length=50,
        description="Employment category: salaried, self_employed, or other",
    )
    requested_amount: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Requested loan principal amount",
    )

    @field_validator("work_type")
    @classmethod
    def validate_work_type(cls, v: str) -> str:
        norm = (v or "").strip().lower()
        if not norm or norm not in ALLOWED_WORK_TYPES:
            raise ValueError(f"Invalid work_type. Allowed values are: {sorted(ALLOWED_WORK_TYPES)}")
        return norm


class LoanApplicationUpdate(BaseModel):
    """Payload for partial updates to an existing draft loan application."""

    model_config = ConfigDict(extra="forbid")

    age: Optional[int] = Field(default=None, gt=0, le=120, description="Applicant age in years")
    monthly_income: Optional[Decimal] = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Applicant monthly income",
    )
    work_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Employment category: salaried, self_employed, or other",
    )
    requested_amount: Optional[Decimal] = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Requested loan principal amount",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_inputs(cls, data):
        if not isinstance(data, dict):
            return data
        if not data:
            raise ValueError("At least one field must be provided for update.")
        for k, v in data.items():
            if v is None:
                raise ValueError(f"Field '{k}' cannot be null.")
        return data

    @field_validator("work_type")
    @classmethod
    def validate_work_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        norm = v.strip().lower()
        if not norm or norm not in ALLOWED_WORK_TYPES:
            raise ValueError(f"Invalid work_type. Allowed values are: {sorted(ALLOWED_WORK_TYPES)}")
        return norm


class LoanApplicationResponse(BaseModel):
    """Public representation of a customer's loan application."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    age: int
    monthly_income: Decimal
    work_type: str
    requested_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
