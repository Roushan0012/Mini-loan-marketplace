"""Strict database safety guards for E2E tests.

Enforces that end-to-end tests and fixtures exclusively target the dedicated
E2E database 'mini_loan_marketplace_e2e' and never target development or
production databases.
"""

from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

EXPECTED_E2E_DATABASE = "mini_loan_marketplace_e2e"

REJECTED_E2E_DATABASES = {
    "mini_loan_marketplace",
    "production",
    "prod",
    "live",
    "mini_loan_marketplace_prod",
    "staging",
}


def validate_e2e_database_name(db_name: Optional[str]) -> str:
    """Validate that the configured E2E database name exactly matches the expected dedicated DB.

    Raises:
        RuntimeError: If db_name is empty, matches known development/production names,
                      or does not match EXPECTED_E2E_DATABASE.
    """
    if not db_name or not isinstance(db_name, str):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: E2E database name cannot be empty. "
            f"Expected '{EXPECTED_E2E_DATABASE}'."
        )

    clean_name = db_name.strip()
    if clean_name != EXPECTED_E2E_DATABASE:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: E2E test suite can only target dedicated database "
            f"'{EXPECTED_E2E_DATABASE}', got '{clean_name}'. Arbitrary overrides, development, "
            f"and production databases are strictly rejected."
        )

    return clean_name


def verify_e2e_database_connection(session: Session) -> str:
    """Query PostgreSQL to verify that the active session is connected to the E2E database.

    Executes 'SELECT current_database()' directly on the connection to prevent
    connection-string spoofing or misdirected session binds.

    Raises:
        RuntimeError: If the connected database does not equal EXPECTED_E2E_DATABASE.
    """
    # 1. Check URL database name
    if session.bind is not None and hasattr(session.bind, "url"):
        url_db = str(session.bind.url.database or "")
        validate_e2e_database_name(url_db)

    # 2. Query live database connection identity
    current_db = session.execute(text("SELECT current_database()")).scalar()
    if not current_db or str(current_db).strip() != EXPECTED_E2E_DATABASE:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Active database connection is connected to '{current_db}', "
            f"expected '{EXPECTED_E2E_DATABASE}'. Aborting to prevent unintended mutations."
        )

    return str(current_db).strip()
