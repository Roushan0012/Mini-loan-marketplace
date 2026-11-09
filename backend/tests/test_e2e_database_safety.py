"""Tests for strict E2E database safety guards."""

from unittest.mock import MagicMock
import pytest
from sqlalchemy import text

from app.core.e2e_safety import (
    EXPECTED_E2E_DATABASE,
    validate_e2e_database_name,
    verify_e2e_database_connection,
)


def test_validate_e2e_database_name_accepts_expected_database() -> None:
    """Validate that only EXPECTED_E2E_DATABASE is accepted."""
    assert validate_e2e_database_name("mini_loan_marketplace_e2e") == "mini_loan_marketplace_e2e"
    assert validate_e2e_database_name(EXPECTED_E2E_DATABASE) == EXPECTED_E2E_DATABASE


@pytest.mark.parametrize(
    "rejected_name",
    [
        "mini_loan_marketplace",
        "production",
        "prod",
        "live",
        "mini_loan_marketplace_prod",
        "staging",
        "some_custom_database",
        "marketplace_test",
        "mini_loan_marketplace_test",
        "e2e_db",
        "test",
        "",
        "   ",
        None,
    ],
)
def test_validate_e2e_database_name_rejects_disallowed_databases(rejected_name: str | None) -> None:
    """Validate that development, production, staging, and arbitrary custom DBs are rejected."""
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        validate_e2e_database_name(rejected_name)  # type: ignore[arg-type]


def test_verify_e2e_database_connection_success() -> None:
    """Verify that when session is connected to EXPECTED_E2E_DATABASE, check succeeds."""
    mock_session = MagicMock()
    mock_session.bind.url.database = EXPECTED_E2E_DATABASE
    mock_session.execute.return_value.scalar.return_value = EXPECTED_E2E_DATABASE

    result = verify_e2e_database_connection(mock_session)
    assert result == EXPECTED_E2E_DATABASE


@pytest.mark.parametrize(
    "mismatched_db",
    [
        "mini_loan_marketplace",
        "production",
        "prod",
        "live",
        "mini_loan_marketplace_prod",
        "staging",
        "some_custom_database",
        "mini_loan_marketplace_test",
    ],
)
def test_verify_e2e_database_connection_rejects_mismatch(mismatched_db: str) -> None:
    """Verify that live connection query mismatch raises a RuntimeError before any mutations."""
    # Case 1: scalar returns mismatched database
    mock_session = MagicMock()
    mock_session.bind.url.database = EXPECTED_E2E_DATABASE
    mock_session.execute.return_value.scalar.return_value = mismatched_db

    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        verify_e2e_database_connection(mock_session)

    # Case 2: URL bind has mismatched database
    mock_session2 = MagicMock()
    mock_session2.bind.url.database = mismatched_db
    mock_session2.execute.return_value.scalar.return_value = EXPECTED_E2E_DATABASE

    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        verify_e2e_database_connection(mock_session2)
