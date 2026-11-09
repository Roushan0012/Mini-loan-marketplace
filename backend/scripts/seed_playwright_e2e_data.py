#!/usr/bin/env python3
"""E2E Test Data Seeder strictly for the dedicated 'mini_loan_marketplace_e2e' database.

SAFETY REQUIREMENTS:
- Strictly verifies connection identity: SELECT current_database() == 'mini_loan_marketplace_e2e'.
- Refuses to run against any other database.
- Idempotently creates test accounts for Customer, Caller, and Admin.
- Assigns test leads to Caller.
- Seeds canonical lender policies if not already present.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

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

CUSTOMER_EMAIL = os.getenv("E2E_CUSTOMER_EMAIL", "e2e_customer_playwright@example.com")
CUSTOMER_PASSWORD = os.getenv("E2E_CUSTOMER_PASSWORD", "E2ePlaywrightPassword123!")

CALLER_EMAIL = os.getenv("E2E_CALLER_EMAIL", "e2e_caller_playwright@example.com")
CALLER_PASSWORD = os.getenv("E2E_CALLER_PASSWORD", "E2ePlaywrightPassword123!")

ADMIN_EMAIL = os.getenv("E2E_ADMIN_EMAIL", "e2e_admin_playwright@example.com")
ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "E2ePlaywrightPassword123!")


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
    session = get_e2e_session()
    try:
        # Seed policies
        seed_lender_policies(session=session, enforce_dev_guard=False)

        # 1. Customer User
        cust_user = session.query(User).filter(User.email == CUSTOMER_EMAIL).first()
        if not cust_user:
            cust_user = User(
                email=CUSTOMER_EMAIL,
                password_hash=hash_password(CUSTOMER_PASSWORD),
                role="customer",
                full_name="E2E Playwright Customer",
                is_active=True,
            )
            session.add(cust_user)
        else:
            cust_user.password_hash = hash_password(CUSTOMER_PASSWORD)
            cust_user.is_active = True
        session.commit()
        session.refresh(cust_user)

        # 2. Caller User
        caller_user = session.query(User).filter(User.email == CALLER_EMAIL).first()
        if not caller_user:
            caller_user = User(
                email=CALLER_EMAIL,
                password_hash=hash_password(CALLER_PASSWORD),
                role="caller",
                full_name="E2E Playwright Caller",
                is_active=True,
            )
            session.add(caller_user)
        else:
            caller_user.password_hash = hash_password(CALLER_PASSWORD)
            caller_user.is_active = True
        session.commit()
        session.refresh(caller_user)

        # 3. Other Caller User (for testing isolation)
        other_caller_email = "e2e_other_caller@example.com"
        other_caller = session.query(User).filter(User.email == other_caller_email).first()
        if not other_caller:
            other_caller = User(
                email=other_caller_email,
                password_hash=hash_password("E2ePlaywrightPassword123!"),
                role="caller",
                full_name="Other Caller",
                is_active=True,
            )
            session.add(other_caller)
            session.commit()
            session.refresh(other_caller)

        # 4. Admin User
        admin_user = session.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin_user:
            admin_user = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
                full_name="E2E Playwright Admin",
                is_active=True,
            )
            session.add(admin_user)
        else:
            admin_user.password_hash = hash_password(ADMIN_PASSWORD)
            admin_user.is_active = True
        session.commit()
        session.refresh(admin_user)

        # 5. Assigned Lead for CALLER_EMAIL
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

        # 6. Assigned Lead for OTHER caller (should NOT be visible to CALLER_EMAIL)
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

        print("Successfully seeded Playwright E2E data in 'mini_loan_marketplace_e2e'.")
    finally:
        session.close()


if __name__ == "__main__":
    seed_e2e_users_and_leads()
