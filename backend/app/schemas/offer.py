from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MockOfferTerms(BaseModel):
    """Pydantic model representing structured versioned mock offer terms.

    Stored in the nullable JSONB 'offer_terms' column in lender_policies.

    Financial Precision:
    All financial percentages and amounts use Decimal representations.
    Floating-point numbers are strictly forbidden to prevent precision drift.
    """

    model_config = ConfigDict(extra="forbid")

    apr_percent: Decimal = Field(
        ...,
        ge=Decimal("0.0000"),
        le=Decimal("100.0000"),
        max_digits=7,
        decimal_places=4,
        description="Nominal annual percentage rate (APR) between 0 and 100 with up to 4 decimal places",
    )
    term_months: int = Field(
        ...,
        gt=0,
        le=360,
        description="Loan tenure in months (between 1 and 360)",
    )
    max_loan_amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        description="Maximum loan amount permitted under policy with 2 decimal places",
    )

    @field_validator("apr_percent", "max_loan_amount", mode="before")
    @classmethod
    def reject_float(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError(
                "Floating-point values are not permitted for financial calculations; "
                "provide a Decimal or exact numeric string."
            )
        return v
