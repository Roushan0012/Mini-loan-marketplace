import os
import uuid
from collections.abc import Generator
from decimal import Decimal
from typing import Any, Dict, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, settings

# Strictly target the dedicated E2E test database
E2E_DB_NAME = os.getenv("E2E_POSTGRES_DB", "mini_loan_marketplace_e2e")
E2E_WEBHOOK_SECRET = "e2e-webhook-dummy-secret-key-for-hmac-verification-12345678"

# Safety verification: ensure E2E DB is not the development or production database
if E2E_DB_NAME in ("mini_loan_marketplace", "production", "prod", "live"):
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: E2E test suite cannot target "
        f"development or production database '{E2E_DB_NAME}'."
    )

# Create an isolated engine and sessionmaker strictly targeting the E2E database
active_settings = get_settings()
e2e_db_url = URL.create(
    drivername="postgresql+psycopg",
    username=active_settings.POSTGRES_USER,
    password=active_settings.POSTGRES_PASSWORD,
    host=active_settings.POSTGRES_HOST,
    port=active_settings.POSTGRES_PORT,
    database=E2E_DB_NAME,
)
e2e_engine = create_engine(e2e_db_url, pool_pre_ping=True)
E2ESessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=e2e_engine)

from app.core.security import create_access_token, hash_password
from app.core.webhook_security import create_mock_webhook_signature
from app.db.seed_lender_policies import seed_lender_policies
from app.db.session import get_db
from app.main import app
from app.models.consent import Consent
from app.models.lead import Lead
from app.models.lead_assignment import LeadAssignment
from app.models.lender_decision import LenderDecision
from app.models.lender_event import LenderEvent
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from app.models.user import User

E2E_PREFIX = "e2e_"
E2E_CUST_PREFIX = f"{E2E_PREFIX}cust_"
E2E_CALLER_PREFIX = f"{E2E_PREFIX}caller_"
E2E_ADMIN_PREFIX = f"{E2E_PREFIX}admin_"
E2E_LEAD_REF_PREFIX = f"{E2E_PREFIX}lead_"


@pytest.fixture(autouse=True)
def configure_e2e_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the mock lender webhook secret on settings instance for E2E tests."""
    monkeypatch.setattr(settings, "MOCK_LENDER_WEBHOOK_SECRET", E2E_WEBHOOK_SECRET)


@pytest.fixture(autouse=True)
def override_db_for_e2e() -> Generator[None, None, None]:
    """Override FastAPI get_db dependency strictly during E2E test execution."""
    def override_get_db() -> Generator[Session, None, None]:
        db = E2ESessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient connected to the FastAPI application for E2E tests."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def setup_e2e_policies() -> Generator[None, None, None]:
    """Ensure fictional lender policies are seeded in the isolated E2E database."""
    with E2ESessionLocal() as session:
        seed_lender_policies(session=session, enforce_dev_guard=False)
    yield


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a database session strictly connected to the isolated E2E database."""
    session = E2ESessionLocal()
    # Verify safety: session must target E2E database
    db_name = str(session.bind.url.database)
    assert db_name == E2E_DB_NAME, f"Safety guard: session connected to '{db_name}', expected '{E2E_DB_NAME}'"
    assert db_name != "mini_loan_marketplace", "Safety guard: cannot target development database"
    try:
        yield session
    finally:
        session.close()


def _clean_e2e_test_records(session: Session) -> None:
    """Safely delete only E2E test-owned records in foreign-key safe order."""
    db_name = str(session.bind.url.database)
    if db_name != E2E_DB_NAME:
        raise RuntimeError(
            f"Safety guard violation: Refusing to clean records in database '{db_name}'. Expected '{E2E_DB_NAME}'."
        )

    test_user_subquery = session.query(User.id).filter(
        User.email.startswith(E2E_PREFIX)
    )

    test_app_subquery = session.query(LoanApplication.id).filter(
        LoanApplication.customer_id.in_(test_user_subquery)
    )

    test_run_subquery = session.query(MatchRun.id).filter(
        MatchRun.application_id.in_(test_app_subquery)
    )

    # 1. Lender events
    session.query(LenderEvent).filter(
        LenderEvent.submission_id.in_(
            session.query(OfferSubmission.id).filter(
                OfferSubmission.application_id.in_(test_app_subquery)
            )
        )
    ).delete(synchronize_session=False)

    # 2. Offer submissions
    session.query(OfferSubmission).filter(
        OfferSubmission.application_id.in_(test_app_subquery)
    ).delete(synchronize_session=False)

    # 3. Offers
    session.query(Offer).filter(
        Offer.lender_decision_id.in_(
            session.query(LenderDecision.id).filter(
                LenderDecision.match_run_id.in_(test_run_subquery)
            )
        )
    ).delete(synchronize_session=False)

    # 4. Lender decisions
    session.query(LenderDecision).filter(
        LenderDecision.match_run_id.in_(test_run_subquery)
    ).delete(synchronize_session=False)

    # 5. Match runs
    session.query(MatchRun).filter(
        MatchRun.application_id.in_(test_app_subquery)
    ).delete(synchronize_session=False)

    # 6. Consents
    session.query(Consent).filter(
        Consent.application_id.in_(test_app_subquery)
    ).delete(synchronize_session=False)

    # 7. Lead assignments
    session.query(LeadAssignment).filter(
        LeadAssignment.lead_id.in_(
            session.query(Lead.id).filter(
                Lead.synthetic_reference.startswith(E2E_LEAD_REF_PREFIX)
            )
        )
    ).delete(synchronize_session=False)

    session.query(LeadAssignment).filter(
        LeadAssignment.caller_id.in_(test_user_subquery)
    ).delete(synchronize_session=False)

    # 8. Loan applications
    session.query(LoanApplication).filter(
        LoanApplication.customer_id.in_(test_user_subquery)
    ).delete(synchronize_session=False)

    session.query(LoanApplication).filter(
        LoanApplication.lead_id.in_(
            session.query(Lead.id).filter(
                Lead.synthetic_reference.startswith(E2E_LEAD_REF_PREFIX)
            )
        )
    ).delete(synchronize_session=False)

    # 9. Test leads
    session.query(Lead).filter(
        Lead.synthetic_reference.startswith(E2E_LEAD_REF_PREFIX)
    ).delete(synchronize_session=False)

    # 10. Test users
    session.query(User).filter(
        User.email.startswith(E2E_PREFIX)
    ).delete(synchronize_session=False)

    session.commit()


@pytest.fixture(autouse=True)
def cleanup_e2e_records() -> Generator[None, None, None]:
    """Clean up only E2E test-owned records before and after each test."""
    with E2ESessionLocal() as session:
        _clean_e2e_test_records(session)
    yield
    with E2ESessionLocal() as session:
        _clean_e2e_test_records(session)


def create_e2e_user(
    db: Session,
    email: str,
    role: str,
    full_name: str,
    password: str = "E2eTestPassword123!",
) -> Tuple[User, str]:
    """Create an E2E test user and return (User, JWT token)."""
    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.id)
    return user, token


def create_e2e_lead_with_assignment(
    db: Session,
    synthetic_ref: str,
    applicant_name: str,
    caller_id: int,
    amount: Decimal = Decimal("50000.00"),
    status: str = "new",
    work_type: str = "salaried",
) -> Lead:
    """Create an E2E test lead assigned to a caller."""
    lead = Lead(
        synthetic_reference=synthetic_ref,
        applicant_name=applicant_name,
        age=30,
        monthly_income=Decimal("50000.00"),
        work_type=work_type,
        requested_amount=amount,
        status=status,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    assignment = LeadAssignment(
        lead_id=lead.id,
        caller_id=caller_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(lead)
    return lead
