from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class LenderDecisionResponse(BaseModel):
    """Pydantic schema representing the outcome of a single lender policy evaluation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lender_code: str
    lender_name: str
    policy_version_snapshot: str
    decision_status: str
    exclusion_reason_code: Optional[str] = None
    exclusion_reason: Optional[str] = None
    evaluated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_from_orm(cls, data: Any) -> Any:
        """Extract lender_code and lender_name from associated LenderPolicy if passing an ORM model."""
        if hasattr(data, "__dict__") and hasattr(data, "lender_policy"):
            policy = getattr(data, "lender_policy", None)
            return {
                "id": getattr(data, "id", None),
                "lender_code": getattr(data, "lender_code", None)
                or (policy.lender_code if policy else ""),
                "lender_name": getattr(data, "lender_name", None)
                or (policy.lender_name if policy else ""),
                "policy_version_snapshot": getattr(data, "policy_version_snapshot", None),
                "decision_status": getattr(data, "decision_status", None),
                "exclusion_reason_code": getattr(data, "exclusion_reason_code", None),
                "exclusion_reason": getattr(data, "exclusion_reason", None),
                "evaluated_at": getattr(data, "evaluated_at", None),
            }
        return data


class MatchRunResponse(BaseModel):
    """Pydantic schema representing a completed matching run execution and its lender decisions."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    run_number: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    decisions: List[LenderDecisionResponse]


class MatchRunSummaryResponse(BaseModel):
    """Pydantic schema summarizing the full matching history for a loan application."""

    model_config = ConfigDict(from_attributes=True)

    total_runs: int
    runs: List[MatchRunResponse]
