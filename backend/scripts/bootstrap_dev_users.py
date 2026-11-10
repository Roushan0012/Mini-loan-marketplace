#!/usr/bin/env python3
"""Development-only bootstrap script for creating caller and admin user accounts.

SAFETY REQUIREMENTS:
- Development environment only (refuses to run if ENVIRONMENT != 'development').
- Targets only the dedicated development database: mini_loan_marketplace.
- Checks live database connection identity using 'SELECT current_database()'.
- Explicit command-line invocation required.
- No public HTTP exposure or role escalation from customer accounts.
- Password minimum: 12 characters (aligned with UserRegisterRequest).
- Interactive password input via getpass.getpass() by default.
- Non-interactive password entry via BOOTSTRAP_DEV_USER_PASSWORD env variable.
- Passwords are never accepted via command-line arguments to prevent shell history exposure.
- Explicit --update-existing flag required to modify an existing account.
- Never prints passwords or password hashes.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

EXPECTED_DEV_DATABASE = "mini_loan_marketplace"


def validate_bootstrap_environment(env: str, db_name: str) -> None:
    """Validate that environment and database settings target only the local dev database."""
    if env != "development":
        raise RuntimeError(
            f"Safety guard violation: Bootstrapping users is only permitted in "
            f"ENVIRONMENT='development'. Current environment: '{env}'."
        )

    if db_name != EXPECTED_DEV_DATABASE:
        raise RuntimeError(
            f"Safety guard violation: Refusing to bootstrap users against database '{db_name}'. "
            f"Expected dedicated development database '{EXPECTED_DEV_DATABASE}'."
        )


def verify_bootstrap_database_connection(session: Session) -> str:
    """Query live connection identity to ensure connection is to the expected dev database."""
    current_db = session.execute(text("SELECT current_database()")).scalar()
    if not current_db or str(current_db).strip() != EXPECTED_DEV_DATABASE:
        raise RuntimeError(
            f"Safety guard violation: Connected database is '{current_db}', "
            f"expected '{EXPECTED_DEV_DATABASE}'."
        )
    return str(current_db).strip()


def bootstrap_user(
    email: str,
    password: str,
    role: str,
    full_name: str,
    update_existing: bool = False,
    session: Optional[Session] = None,
) -> User:
    """Bootstrap a caller or admin user in the local development database."""
    validate_bootstrap_environment(settings.ENVIRONMENT, settings.POSTGRES_DB)

    if role not in ("caller", "admin"):
        raise ValueError(f"Role must be 'caller' or 'admin', got '{role}'.")

    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")

    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise ValueError(f"Invalid email address: '{email}'.")

    close_session = False
    db = session
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        verify_bootstrap_database_connection(db)

        existing = db.query(User).filter(User.email == normalized_email).first()
        if existing:
            if not update_existing:
                raise RuntimeError(
                    f"User '{normalized_email}' already exists. Pass --update-existing "
                    f"to update an existing development account."
                )

            if existing.role == "customer":
                raise RuntimeError(
                    f"Safety guard violation: Refusing to escalate existing customer "
                    f"account '{normalized_email}' to privileged role '{role}'."
                )

            existing.role = role
            existing.password_hash = hash_password(password)
            existing.full_name = full_name.strip()
            existing.is_active = True
            db.commit()
            db.refresh(existing)
            print(
                f"User '{normalized_email}' updated successfully with role '{role}' (ID: {existing.id})."
            )
            return existing
        else:
            new_user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                role=role,
                full_name=full_name.strip(),
                is_active=True,
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            print(
                f"User '{normalized_email}' created successfully with role '{role}' (ID: {new_user.id})."
            )
            return new_user
    finally:
        if close_session and db is not None:
            db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap developer caller or admin accounts in development environment."
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=["caller", "admin"],
        help="Account role to create or update ('caller' or 'admin').",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address for the bootstrap account.",
    )
    parser.add_argument(
        "--full-name",
        default="",
        help="Full display name for the account.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Explicitly permit updating an existing development caller or admin account.",
    )

    args = parser.parse_args()

    # Determine password securely (env var or interactive prompt; no CLI argument)
    env_password = os.getenv("BOOTSTRAP_DEV_USER_PASSWORD")
    if env_password and env_password.strip():
        password = env_password.strip()
    else:
        try:
            password = getpass.getpass("Enter password (minimum 12 characters): ")
        except (EOFError, KeyboardInterrupt):
            print("\nPassword prompt cancelled.", file=sys.stderr)
            sys.exit(1)

    if not password:
        print("Error: Password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    full_name = args.full_name or ("Dev Caller" if args.role == "caller" else "Dev Admin")

    try:
        bootstrap_user(
            email=args.email,
            password=password,
            role=args.role,
            full_name=full_name,
            update_existing=args.update_existing,
        )
    except Exception as e:
        print(f"Error bootstrapping user: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
