from typing import Literal

from pydantic import BaseModel, ConfigDict


class MockSubmissionReceipt(BaseModel):
    """Deterministic receipt returned by the mock lender adapter upon dispatch."""

    model_config = ConfigDict(frozen=True)

    mock_reference: str
    status: Literal["submitted"] = "submitted"
