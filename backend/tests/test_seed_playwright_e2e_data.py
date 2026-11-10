"""Unit tests for Playwright E2E data seeder validation and safety guards."""

import pytest

from scripts.seed_playwright_e2e_data import (
    get_required_credential,
    validate_e2e_credentials,
)


def test_get_required_credential_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that an absent credential variable raises ValueError displaying the variable name."""
    monkeypatch.delenv("E2E_CUSTOMER_EMAIL", raising=False)
    with pytest.raises(ValueError, match="Missing required environment variable: E2E_CUSTOMER_EMAIL"):
        get_required_credential("E2E_CUSTOMER_EMAIL")


def test_validate_e2e_credentials_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that properly configured distinct E2E credentials validate successfully."""
    monkeypatch.setenv("E2E_CUSTOMER_EMAIL", "e2e_cust_valid@example.com")
    monkeypatch.setenv("E2E_CUSTOMER_PASSWORD", "CustPassword123!")
    monkeypatch.setenv("E2E_CALLER_EMAIL", "e2e_caller_valid@example.com")
    monkeypatch.setenv("E2E_CALLER_PASSWORD", "CallerPassword123!")
    monkeypatch.setenv("E2E_ADMIN_EMAIL", "e2e_admin_valid@example.com")
    monkeypatch.setenv("E2E_ADMIN_PASSWORD", "AdminPassword123!")

    cust, caller, admin = validate_e2e_credentials()
    assert cust["email"] == "e2e_cust_valid@example.com"
    assert caller["email"] == "e2e_caller_valid@example.com"
    assert admin["email"] == "e2e_admin_valid@example.com"


def test_validate_e2e_credentials_rejects_missing_e2e_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that email addresses missing the 'e2e_' prefix are rejected."""
    monkeypatch.setenv("E2E_CUSTOMER_EMAIL", "normal_user@example.com")
    monkeypatch.setenv("E2E_CUSTOMER_PASSWORD", "CustPassword123!")
    monkeypatch.setenv("E2E_CALLER_EMAIL", "e2e_caller_valid@example.com")
    monkeypatch.setenv("E2E_CALLER_PASSWORD", "CallerPassword123!")
    monkeypatch.setenv("E2E_ADMIN_EMAIL", "e2e_admin_valid@example.com")
    monkeypatch.setenv("E2E_ADMIN_PASSWORD", "AdminPassword123!")

    with pytest.raises(ValueError, match="must start with 'e2e_' prefix"):
        validate_e2e_credentials()


def test_validate_e2e_credentials_rejects_short_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that passwords shorter than 12 characters are rejected."""
    monkeypatch.setenv("E2E_CUSTOMER_EMAIL", "e2e_cust_valid@example.com")
    monkeypatch.setenv("E2E_CUSTOMER_PASSWORD", "Short123!")  # 9 chars
    monkeypatch.setenv("E2E_CALLER_EMAIL", "e2e_caller_valid@example.com")
    monkeypatch.setenv("E2E_CALLER_PASSWORD", "CallerPassword123!")
    monkeypatch.setenv("E2E_ADMIN_EMAIL", "e2e_admin_valid@example.com")
    monkeypatch.setenv("E2E_ADMIN_PASSWORD", "AdminPassword123!")

    with pytest.raises(ValueError, match="must have at least 12 characters"):
        validate_e2e_credentials()


def test_validate_e2e_credentials_rejects_duplicate_emails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that identical email addresses across roles are rejected."""
    monkeypatch.setenv("E2E_CUSTOMER_EMAIL", "e2e_shared@example.com")
    monkeypatch.setenv("E2E_CUSTOMER_PASSWORD", "CustPassword123!")
    monkeypatch.setenv("E2E_CALLER_EMAIL", "e2e_shared@example.com")  # Duplicate
    monkeypatch.setenv("E2E_CALLER_PASSWORD", "CallerPassword123!")
    monkeypatch.setenv("E2E_ADMIN_EMAIL", "e2e_admin_valid@example.com")
    monkeypatch.setenv("E2E_ADMIN_PASSWORD", "AdminPassword123!")

    with pytest.raises(ValueError, match="emails for customer, caller, and admin must be distinct"):
        validate_e2e_credentials()


def test_validate_e2e_credentials_rejects_duplicate_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that identical passwords across roles are rejected."""
    monkeypatch.setenv("E2E_CUSTOMER_EMAIL", "e2e_cust_valid@example.com")
    monkeypatch.setenv("E2E_CUSTOMER_PASSWORD", "SameSharedPassword123!")
    monkeypatch.setenv("E2E_CALLER_EMAIL", "e2e_caller_valid@example.com")
    monkeypatch.setenv("E2E_CALLER_PASSWORD", "SameSharedPassword123!")  # Duplicate
    monkeypatch.setenv("E2E_ADMIN_EMAIL", "e2e_admin_valid@example.com")
    monkeypatch.setenv("E2E_ADMIN_PASSWORD", "AdminPassword123!")

    with pytest.raises(ValueError, match="passwords for customer, caller, and admin must be distinct"):
        validate_e2e_credentials()
