from decimal import Decimal
from typing import List, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_WORK_TYPES: Set[str] = {"salaried", "self_employed", "other"}


class LenderPolicyRules(BaseModel):
    """Pydantic model representing structured underwriting rules stored in JSONB.

    Compatible with the JSONB 'rules' column in lender_policies.

    Invalid Stored JSON Handling:
    If a database record contains malformed or unparseable JSONB rules, the
    matching engine will intercept validation errors at evaluation time, treat
    the policy definition as corrupted/ineligible, log diagnostic configuration
    telemetry, and emit an explicit ineligible decision or diagnostic error
    without crashing the overall multi-lender matching run.
    """

    model_config = ConfigDict(extra="forbid")

    min_age: int = Field(
        ...,
        gt=0,
        le=100,
        description="Minimum applicant age permitted by lender policy",
    )
    min_monthly_income: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Minimum monthly income required in local currency units",
    )
    allowed_work_types: List[str] = Field(
        ...,
        min_length=1,
        description="Non-empty list of permitted employment categories",
    )

    @field_validator("allowed_work_types")
    @classmethod
    def validate_allowed_work_types(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("allowed_work_types cannot be empty.")

        normalized_types: List[str] = []
        seen: Set[str] = set()

        for item in v:
            norm = (item or "").strip().lower()
            if not norm or norm not in ALLOWED_WORK_TYPES:
                raise ValueError(
                    f"Invalid work type '{item}'. Allowed values are: {sorted(ALLOWED_WORK_TYPES)}"
                )
            if norm in seen:
                raise ValueError(f"Duplicate work type '{norm}' is not permitted.")
            seen.add(norm)
            normalized_types.append(norm)

        return normalized_types
