class MockLenderAdapterError(Exception):
    """Base exception raised for mock lender adapter errors."""

    pass


class UnsupportedLenderCodeError(MockLenderAdapterError):
    """Raised when an unrecognized lender code is passed to the mock lender adapter."""

    pass
