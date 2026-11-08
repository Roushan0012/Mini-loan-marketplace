from typing import Set

from app.integrations.mock_lenders.base import UnsupportedLenderCodeError
from app.integrations.mock_lenders.schemas import MockSubmissionReceipt

SUPPORTED_MOCK_LENDERS: Set[str] = {
    "APEX_FINANCIAL",
    "HORIZON_CREDIT",
    "STERLING_LOANS",
}


class MockLenderClient:
    """Deterministic local-only mock lender adapter for training simulation."""

    def __init__(self, supported_lenders: Set[str] = SUPPORTED_MOCK_LENDERS) -> None:
        self.supported_lenders = supported_lenders

    def submit_offer(self, lender_code: str, submission_id: int) -> MockSubmissionReceipt:
        """Deterministically simulate dispatching an offer to a fictional lender.

        Guarantees:
        - Entirely local and deterministic.
        - No network calls or HTTP clients used.
        - No customer PII transmitted or processed.
        - Deterministic fictional reference format: MOCK-SUB-{lender_code}-{submission_id}.
        - Only supported mock lender codes are permitted.
        """
        if lender_code not in self.supported_lenders:
            raise UnsupportedLenderCodeError(
                f"Unsupported mock lender code: '{lender_code}'. "
                f"Configured lenders: {sorted(self.supported_lenders)}"
            )

        mock_reference = f"MOCK-SUB-{lender_code}-{submission_id}"
        return MockSubmissionReceipt(mock_reference=mock_reference, status="submitted")


mock_lender_client = MockLenderClient()
