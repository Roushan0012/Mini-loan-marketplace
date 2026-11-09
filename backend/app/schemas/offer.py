from datetime import datetime
from decimal import Decimal
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MockOfferTerms(BaseModel):
    """Pydantic model representing structured versioned mock offer terms.

    Stored in the nullable JSONB 'offer_terms' column in lender_policies.

    Financial Precision:
    All financial percentages and amounts use Decimal representations.
    Floating-point numbers are strictly forbidden to prevent precision drift.
    Tenure in months strictly requires integer type (booleans rejected).
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
        strict=True,
        gt=0,
        le=360,
        description="Loan tenure in months (between 1 and 360, strictly integer)",
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


class OfferResponse(BaseModel):
    """Pydantic schema representing a credit offer extended by a mock lender."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lender_decision_id: int
    lender_code: str
    lender_name: str
    policy_version: str
    loan_amount: Decimal
    apr: Decimal
    term_months: int
    monthly_installment: Decimal
    mock_kfs_reference: str
    status: str
    created_at: datetime
    valid_until: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def extract_from_orm(cls, data: Any) -> Any:
        """Extract lender_code, lender_name, policy_version from lender_decision/policy if passing ORM model."""
        if hasattr(data, "__dict__") and hasattr(data, "lender_decision"):
            decision = getattr(data, "lender_decision", None)
            policy = getattr(decision, "lender_policy", None) if decision else None
            return {
                "id": getattr(data, "id", None),
                "lender_decision_id": getattr(data, "lender_decision_id", None),
                "lender_code": getattr(data, "lender_code", None)
                or (policy.lender_code if policy else ""),
                "lender_name": getattr(data, "lender_name", None)
                or (policy.lender_name if policy else ""),
                "policy_version": getattr(data, "policy_version", None)
                or (
                    decision.policy_version_snapshot
                    if decision
                    else (policy.policy_version if policy else "")
                ),
                "loan_amount": getattr(data, "loan_amount", None),
                "apr": getattr(data, "apr", None),
                "term_months": getattr(data, "term_months", None),
                "monthly_installment": getattr(data, "monthly_installment", None),
                "mock_kfs_reference": getattr(data, "mock_kfs_reference", None),
                "status": getattr(data, "status", None),
                "created_at": getattr(data, "created_at", None),
                "valid_until": getattr(data, "valid_until", None),
            }
        return data


class OfferGenerationResponse(BaseModel):
    """Pydantic schema representing the outcome of an offer generation execution."""

    model_config = ConfigDict(from_attributes=True)

    application_id: int
    match_run_id: Optional[int] = None
    run_number: Optional[int] = None
    generated_count: int
    offers: List[OfferResponse]


class MockKFSResponse(BaseModel):
    """Pydantic v2 schema representing a Key Facts Statement (KFS) disclosure in the mock environment."""

    model_config = ConfigDict(from_attributes=True)

    # Document Identification
    document_type: Literal["TRAINING_ONLY_MOCK_KFS"] = "TRAINING_ONLY_MOCK_KFS"
    document_version: Literal["training-v1"] = "training-v1"
    mock_kfs_reference: str
    offer_id: int
    application_id: int

    # Lender Information
    lender_code: str
    lender_name: str
    policy_version: str

    # Offer Status
    offer_status: str
    offer_created_at: datetime
    valid_until: Optional[datetime] = None

    # Financial Information
    loan_amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        description="Principal loan amount extended",
    )
    nominal_annual_apr_percent: Decimal = Field(
        ...,
        ge=Decimal("0.0000"),
        le=Decimal("100.0000"),
        max_digits=7,
        decimal_places=4,
        description="Nominal Annual Percentage Rate (APR)",
    )
    term_months: int = Field(
        ...,
        strict=True,
        gt=0,
        le=360,
        description="Loan tenure in months",
    )
    number_of_installments: int = Field(
        ...,
        strict=True,
        gt=0,
        le=360,
        description="Total number of scheduled monthly installments",
    )
    payment_frequency: str = "Monthly"
    monthly_installment: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        description="Equated Monthly Installment (EMI)",
    )
    estimated_total_repayment: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        max_digits=14,
        decimal_places=2,
        description="Estimated aggregate repayment over the full tenure",
    )
    estimated_total_interest: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        max_digits=14,
        decimal_places=2,
        description="Estimated aggregate interest payable over the full tenure",
    )
    amortization_method: str = "Monthly reducing-balance"

    # Disclosures
    fee_disclosure: str
    calculation_disclosure: str
    training_disclosure: str

    @field_validator(
        "loan_amount",
        "nominal_annual_apr_percent",
        "monthly_installment",
        "estimated_total_repayment",
        "estimated_total_interest",
        mode="before",
    )
    @classmethod
    def reject_float(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError(
                "Floating-point values are not permitted for financial calculations; "
                "provide a Decimal or exact numeric string."
            )
        return v


class OfferSelectionResponse(BaseModel):
    """Pydantic v2 schema representing the outcome of selecting a loan offer."""

    model_config = ConfigDict(from_attributes=True)

    application_id: int
    application_status: Literal["offer_selected"] = "offer_selected"
    selected_offer: OfferResponse
    withdrawn_offer_count: int
    selection_result: Literal["selected", "already_selected"]


class OfferSubmissionResponse(BaseModel):
    """Pydantic v2 schema representing the outcome of submitting an offer to a mock lender."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    offer_id: int
    lender_code: str
    lender_name: str
    policy_version: str
    status: Literal[
        "pending",
        "submitted",
        "accepted",
        "declined",
        "timed_out",
        "failed",
    ]
    mock_reference: Optional[str] = None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime
    submission_result: Literal["created", "replayed"]


class OfferSubmissionStatusResponse(BaseModel):
    """Pydantic v2 schema representing the current state of an application's offer submission."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    offer_id: int
    lender_code: str
    lender_name: str
    policy_version: str
    status: Literal[
        "pending",
        "submitted",
        "accepted",
        "declined",
        "timed_out",
        "failed",
    ]
    mock_reference: Optional[str] = None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime
