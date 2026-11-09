#!/usr/bin/env python3
"""Development-only bootstrap script for creating caller and admin user accounts.

SAFETY REQUIREMENTS:
- Development environment only (refuses to run if ENVIRONMENT != 'development').
- Explicit command-line invocation required.
- No public HTTP exposure or role escalation.
- No hardcoded default passwords permitted.
- Enforces strong password requirements (min 8 chars).
"""

import argparse
import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def bootstrap_user(
    email: str,
    password: str,
    role: str,
    full_name: str,
) -> User:
    """Bootstrap a user in the local development database."""
    if settings.ENVIRONMENT != "development":
        raise RuntimeError(
            f"Safety guard violation: Bootstrapping users is only permitted in "
            f"ENVIRONMENT='development'. Current environment: '{settings.ENVIRONMENT}'."
        )

    if settings.POSTGRES_DB in ("production", "prod", "live"):
        raise RuntimeError(
            f"Safety guard violation: Refusing to bootstrap users against database '{settings.POSTGRES_DB}'."
        )

    if role not in ("caller", "admin"):
        raise ValueError(f"Role must be 'caller' or 'admin', got '{role}'.")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise ValueError(f"Invalid email address: '{email}'.")

    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == normalized_email).first()
        if existing:
            print(f"User '{normalized_email}' already exists with role '{existing.role}'. Updating role and password...")
            existing.role = role
            existing.password_hash = hash_password(password)
            existing.full_name = full_name.strip()
            existing.is_active = True
            db.commit()
            db.refresh(existing)
            print(f"User '{normalized_email}' updated successfully (ID: {existing.id}).")
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
            print(f"User '{normalized_email}' created successfully with role '{role}' (ID: {new_user.id}).")
            return new_user


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
        "--password",
        required=True,
        help="Password for the bootstrap account (minimum 8 characters).",
    )
    parser.add_argument(
        "--full-name",
        default="",
        help="Full display name for the account.",
    )

    args = parser.parse_args()

    full_name = args.full_name or ("Dev Caller" if args.role == "caller" else "Dev Admin")

    try:
        bootstrap_user(
            email=args.email,
            password=args.password,
            role=args.role,
            full_name=full_name,
        )
    except Exception as e:
        print(f"Error bootstrapping user: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
