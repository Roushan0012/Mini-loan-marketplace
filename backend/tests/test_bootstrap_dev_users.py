"""Unit tests for development user bootstrap script and safety guards."""

from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.models.user import User
from scripts.bootstrap_dev_users import (
    EXPECTED_DEV_DATABASE,
    bootstrap_user,
    validate_bootstrap_environment,
    verify_bootstrap_database_connection,
)


def test_validate_bootstrap_environment_success() -> None:
    """Validate that environment and db matching expected development configuration succeeds."""
    validate_bootstrap_environment("development", "mini_loan_marketplace")


@pytest.mark.parametrize(
    "invalid_env",
    ["production", "prod", "staging", "test", "development_staging"],
)
def test_validate_bootstrap_environment_rejects_wrong_env(invalid_env: str) -> None:
    """Validate that non-development environments are strictly rejected."""
    with pytest.raises(RuntimeError, match="ENVIRONMENT='development'"):
        validate_bootstrap_environment(invalid_env, "mini_loan_marketplace")


@pytest.mark.parametrize(
    "invalid_db",
    [
        "production",
        "prod",
        "live",
        "mini_loan_marketplace_prod",
        "mini_loan_marketplace_test",
        "mini_loan_marketplace_e2e",
        "arbitrary_db",
    ],
)
def test_validate_bootstrap_environment_rejects_wrong_database(invalid_db: str) -> None:
    """Validate that any database other than mini_loan_marketplace is rejected."""
    with pytest.raises(RuntimeError, match="Refusing to bootstrap users against database"):
        validate_bootstrap_environment("development", invalid_db)


def test_verify_bootstrap_database_connection_rejects_mismatch() -> None:
    """Verify that connection to a mismatched DB raises RuntimeError."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace_test"

    with pytest.raises(RuntimeError, match="Safety guard violation: Connected database is"):
        verify_bootstrap_database_connection(mock_session)


def test_bootstrap_user_insufficient_password_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that passwords shorter than 12 characters are rejected."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "POSTGRES_DB", "mini_loan_marketplace")

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace"

    with pytest.raises(ValueError, match="Password must be at least 12 characters long"):
        bootstrap_user(
            email="test_caller@example.com",
            password="Short1!",  # 7 chars < 12
            role="caller",
            full_name="Test Caller",
            session=mock_session,
        )


def test_bootstrap_user_invalid_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that roles other than caller and admin are rejected."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "POSTGRES_DB", "mini_loan_marketplace")

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace"

    with pytest.raises(ValueError, match="Role must be 'caller' or 'admin'"):
        bootstrap_user(
            email="test_cust@example.com",
            password="ValidPassword123!",
            role="customer",  # Customer creation prohibited via bootstrap
            full_name="Test Customer",
            session=mock_session,
        )


def test_bootstrap_caller_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify creating a new caller user account."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "POSTGRES_DB", "mini_loan_marketplace")

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace"
    mock_session.query.return_value.filter.return_value.first.return_value = None

    created_user = bootstrap_user(
        email="new_caller@example.com",
        password="ValidPassword123!",
        role="caller",
        full_name="New Caller",
        session=mock_session,
    )

    assert created_user.email == "new_caller@example.com"
    assert created_user.role == "caller"
    assert created_user.full_name == "New Caller"
    assert created_user.is_active is True
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_bootstrap_admin_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify creating a new admin user account."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "POSTGRES_DB", "mini_loan_marketplace")

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace"
    mock_session.query.return_value.filter.return_value.first.return_value = None

    created_user = bootstrap_user(
        email="new_admin@example.com",
        password="ValidPassword123!",
        role="admin",
        full_name="New Admin",
        session=mock_session,
    )

    assert created_user.email == "new_admin@example.com"
    assert created_user.role == "admin"
    assert created_user.full_name == "New Admin"
    assert created_user.is_active is True
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_bootstrap_existing_user_without_update_existing_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify modifying existing user without --update-existing raises error."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "POSTGRES_DB", "mini_loan_marketplace")

    existing_user = User(
        email="existing_caller@example.com",
        role="caller",
        full_name="Old Caller",
        password_hash="somehash",
    )

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace"
    mock_session.query.return_value.filter.return_value.first.return_value = existing_user

    with pytest.raises(RuntimeError, match="already exists. Pass --update-existing"):
        bootstrap_user(
            email="existing_caller@example.com",
            password="NewPassword123!",
            role="caller",
            full_name="Updated Caller",
            update_existing=False,
            session=mock_session,
        )


def test_bootstrap_existing_user_with_update_existing_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify modifying existing caller/admin user with --update-existing succeeds."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "POSTGRES_DB", "mini_loan_marketplace")

    existing_user = User(
        email="existing_caller@example.com",
        role="caller",
        full_name="Old Caller",
        password_hash="somehash",
    )
    existing_user.id = 42

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace"
    mock_session.query.return_value.filter.return_value.first.return_value = existing_user

    updated_user = bootstrap_user(
        email="existing_caller@example.com",
        password="NewPassword123!",
        role="admin",  # Can switch between dev staff roles
        full_name="Updated Admin",
        update_existing=True,
        session=mock_session,
    )

    assert updated_user.role == "admin"
    assert updated_user.full_name == "Updated Admin"
    mock_session.commit.assert_called_once()


def test_bootstrap_existing_customer_escalation_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that an existing customer cannot be escalated to caller or admin."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "POSTGRES_DB", "mini_loan_marketplace")

    existing_customer = User(
        email="customer@example.com",
        role="customer",
        full_name="Real Customer",
        password_hash="somehash",
    )
    existing_customer.id = 99

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = "mini_loan_marketplace"
    mock_session.query.return_value.filter.return_value.first.return_value = existing_customer

    with pytest.raises(RuntimeError, match="Refusing to escalate existing customer"):
        bootstrap_user(
            email="customer@example.com",
            password="NewPassword123!",
            role="admin",
            full_name="Escalated Admin",
            update_existing=True,
            session=mock_session,
        )
