#!/usr/bin/env python3
"""E2E Test Data Seeder strictly for the dedicated 'mini_loan_marketplace_e2e' database.

SAFETY REQUIREMENTS:
- Strictly verifies connection identity: SELECT current_database() == 'mini_loan_marketplace_e2e'.
- Refuses to run against any other database.
- Requires E2E credentials via environment variables:
  E2E_CUSTOMER_EMAIL, E2E_CUSTOMER_PASSWORD,
  E2E_CALLER_EMAIL, E2E_CALLER_PASSWORD,
  E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD.
- Enforces 'e2e_' prefix on all email addresses.
- Enforces >= 12 characters for all passwords.
- Validates that credentials for different roles are distinct.
- Never prints passwords or password hashes.
- Confines all user mutations strictly to accounts with 'e2e_' prefix.
- Seeds canonical lender policies if not already present.
"""

import os
import secrets
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, Tuple

# Add backend root to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.e2e_safety import EXPECTED_E2E_DATABASE, validate_e2e_database_name, verify_e2e_database_connection
from app.core.security import hash_password
from app.db.seed_lender_policies import seed_lender_policies
from app.models.lead import Lead
from app.models.lead_assignment import LeadAssignment
from app.models.user import User


def load_local_e2e_env_if_present() -> None:
    """Parse .env.e2e.local if it exists and variables are not already in os.environ."""
    repo_root = backend_dir.parent
    possible_paths = [
        repo_root / ".env.e2e.local",
        backend_dir / ".env.e2e.local",
        Path.cwd() / ".env.e2e.local",
        Path.cwd().parent / ".env.e2e.local",
    ]

    for env_path in possible_paths:
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("#"):
                        continue
                    if "=" in trimmed:
                        k, v = trimmed.split("=", 1)
                        clean_k = k.strip()
                        clean_v = v.strip().strip("'\"")
                        if clean_k and clean_k not in os.environ and clean_v:
                            os.environ[clean_k] = clean_v
            except Exception:
                pass
            break


def get_required_credential(var_name: str) -> str:
    """Get required credential or raise error displaying the variable name only."""
    val = os.getenv(var_name, "").strip()
    if not val:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return val


def validate_e2e_credentials() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """Validate all required E2E credentials for presence, format, length, and uniqueness."""
    load_local_e2e_env_if_present()

    cust_email = get_required_credential("E2E_CUSTOMER_EMAIL")
    cust_password = get_required_credential("E2E_CUSTOMER_PASSWORD")

    caller_email = get_required_credential("E2E_CALLER_EMAIL")
    caller_password = get_required_credential("E2E_CALLER_PASSWORD")

    admin_email = get_required_credential("E2E_ADMIN_EMAIL")
    admin_password = get_required_credential("E2E_ADMIN_PASSWORD")

    roles_data = [
        ("customer", cust_email, cust_password, "E2E_CUSTOMER_EMAIL", "E2E_CUSTOMER_PASSWORD"),
        ("caller", caller_email, caller_password, "E2E_CALLER_EMAIL", "E2E_CALLER_PASSWORD"),
        ("admin", admin_email, admin_password, "E2E_ADMIN_EMAIL", "E2E_ADMIN_PASSWORD"),
    ]

    for role, email, password, email_var, pwd_var in roles_data:
        if not email.lower().startswith("e2e_"):
            raise ValueError(
                f"Invalid {email_var}: E2E test email for role '{role}' must start with 'e2e_' prefix."
            )
        if "@" not in email or "." not in email:
            raise ValueError(f"Invalid {email_var}: '{email}' is not a valid email address.")
        if len(password) < 12:
            raise ValueError(
                f"Invalid {pwd_var}: E2E password for role '{role}' must have at least 12 characters."
            )

    # Validate distinct emails and passwords across roles
    emails = {cust_email.lower(), caller_email.lower(), admin_email.lower()}
    if len(emails) != 3:
        raise ValueError("Security violation: E2E emails for customer, caller, and admin must be distinct.")

    passwords = {cust_password, caller_password, admin_password}
    if len(passwords) != 3:
        raise ValueError("Security violation: E2E passwords for customer, caller, and admin must be distinct.")

    return (
        {"email": cust_email, "password": cust_password},
        {"email": caller_email, "password": caller_password},
        {"email": admin_email, "password": admin_password},
    )


def get_e2e_session() -> Session:
    """Create a strictly guarded session to the E2E database."""
    target_db = validate_e2e_database_name(
        os.getenv("E2E_POSTGRES_DB", EXPECTED_E2E_DATABASE)
    )
    active_settings = get_settings()
    e2e_db_url = URL.create(
        drivername="postgresql+psycopg",
        username=active_settings.POSTGRES_USER,
        password=active_settings.POSTGRES_PASSWORD,
        host=active_settings.POSTGRES_HOST,
        port=active_settings.POSTGRES_PORT,
        database=target_db,
    )
    engine = create_engine(e2e_db_url, pool_pre_ping=True)
    SessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionMaker()
    verify_e2e_database_connection(session)
    return session


def seed_e2e_users_and_leads() -> None:
    """Seed test accounts and assigned leads in mini_loan_marketplace_e2e."""
    # 1. Validate credentials before database connection
    customer_creds, caller_creds, admin_creds = validate_e2e_credentials()

    # 2. Guarded database connection
    session = get_e2e_session()
    try:
        # Seed policies
        seed_lender_policies(session=session, enforce_dev_guard=False)

        # Helper to safely create or update e2e-prefixed accounts
        def upsert_e2e_user(email: str, password: str, role: str, full_name: str) -> User:
            if not email.lower().startswith("e2e_"):
                raise RuntimeError(
                    f"Security violation: Refusing to create or modify non-e2e user '{email}'."
                )

            user = session.query(User).filter(User.email == email.lower()).first()
            if not user:
                user = User(
                    email=email.lower(),
                    password_hash=hash_password(password),
                    role=role,
                    full_name=full_name,
                    is_active=True,
                )
                session.add(user)
            else:
                if not user.email.startswith("e2e_"):
                    raise RuntimeError(
                        f"Security violation: Refusing to mutate non-e2e user account '{user.email}'."
                    )
                user.password_hash = hash_password(password)
                user.role = role
                user.full_name = full_name
                user.is_active = True
            session.commit()
            session.refresh(user)
            return user

        # 3. Create or update Customer, Caller, and Admin
        cust_user = upsert_e2e_user(
            customer_creds["email"],
            customer_creds["password"],
            role="customer",
            full_name="E2E Playwright Customer",
        )

        caller_user = upsert_e2e_user(
            caller_creds["email"],
            caller_creds["password"],
            role="caller",
            full_name="E2E Playwright Caller",
        )

        admin_user = upsert_e2e_user(
            admin_creds["email"],
            admin_creds["password"],
            role="admin",
            full_name="E2E Playwright Admin",
        )

        # 4. Peer Caller User for testing isolation (assigned unique random secret password)
        other_caller_email = "e2e_caller_isolation_peer@example.com"
        random_peer_secret = secrets.token_urlsafe(16)
        other_caller = upsert_e2e_user(
            other_caller_email,
            random_peer_secret,
            role="caller",
            full_name="E2E Peer Caller",
        )

        # 5. Assigned Lead for Caller User
        lead_ref_1 = "e2e_lead_assigned_caller_1"
        lead1 = session.query(Lead).filter(Lead.synthetic_reference == lead_ref_1).first()
        if not lead1:
            lead1 = Lead(
                synthetic_reference=lead_ref_1,
                applicant_name="Playwright Test Applicant Alpha",
                age=29,
                monthly_income=Decimal("65000.00"),
                work_type="salaried",
                requested_amount=Decimal("150000.00"),
                status="new",
            )
            session.add(lead1)
            session.commit()
            session.refresh(lead1)

        assignment1 = session.query(LeadAssignment).filter(LeadAssignment.lead_id == lead1.id).first()
        if not assignment1:
            assignment1 = LeadAssignment(
                lead_id=lead1.id,
                caller_id=caller_user.id,
            )
            session.add(assignment1)
            session.commit()
        else:
            assignment1.caller_id = caller_user.id
            session.commit()

        # 6. Assigned Lead for Peer Caller (should NOT be visible to Caller User)
        lead_ref_2 = "e2e_lead_other_caller_2"
        lead2 = session.query(Lead).filter(Lead.synthetic_reference == lead_ref_2).first()
        if not lead2:
            lead2 = Lead(
                synthetic_reference=lead_ref_2,
                applicant_name="Confidential Other Applicant",
                age=35,
                monthly_income=Decimal("80000.00"),
                work_type="self_employed",
                requested_amount=Decimal("300000.00"),
                status="in_progress",
            )
            session.add(lead2)
            session.commit()
            session.refresh(lead2)

        assignment2 = session.query(LeadAssignment).filter(LeadAssignment.lead_id == lead2.id).first()
        if not assignment2:
            assignment2 = LeadAssignment(
                lead_id=lead2.id,
                caller_id=other_caller.id,
            )
            session.add(assignment2)
            session.commit()
        else:
            assignment2.caller_id = other_caller.id
            session.commit()

        print(
            f"Successfully seeded Playwright E2E data for accounts: "
            f"{cust_user.email}, {caller_user.email}, {admin_user.email} in '{EXPECTED_E2E_DATABASE}'."
        )
    finally:
        session.close()


if __name__ == "__main__":
    try:
        seed_e2e_users_and_leads()
    except Exception as e:
        print(f"Error seeding E2E data: {e}", file=sys.stderr)
        sys.exit(1)
