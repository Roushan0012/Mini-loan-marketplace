import os
from collections.abc import Generator
from decimal import Decimal
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure tests run against the isolated test database and isolated test secret
os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "mini_loan_marketplace_test")
os.environ["JWT_SECRET_KEY"] = os.getenv(
    "TEST_JWT_SECRET_KEY", "test-isolated-dummy-secret-key-for-auth-testing-12345678"
)

from app.core.config import get_settings

get_settings.cache_clear()

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
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

TEST_EMAIL_PREFIX = "pytest_auth_"
TEST_RBAC_EMAIL_PREFIX = "pytest_rbac_"
TEST_RBAC_REF_PREFIX = "pytest_rbac_"
TEST_APP_EMAIL_PREFIX = "pytest_app_"
TEST_CONSENT_EMAIL_PREFIX = "pytest_consent_"
TEST_MATCHING_EMAIL_PREFIX = "pytest_matching_"
TEST_OFFER_EMAIL_PREFIX = "pytest_offer_"
TEST_KFS_EMAIL_PREFIX = "pytest_kfs_"
TEST_SELECT_EMAIL_PREFIX = "pytest_select_"
TEST_SUBMISSION_EMAIL_PREFIX = "pytest_sub_"


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient connected to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a database session to the isolated test database."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _clean_all_test_records(session: Session) -> None:
    """Safely delete test records in foreign-key-safe order."""
    test_user_subquery = session.query(User.id).filter(
        User.email.startswith(TEST_RBAC_EMAIL_PREFIX)
        | User.email.startswith(TEST_EMAIL_PREFIX)
        | User.email.startswith(TEST_APP_EMAIL_PREFIX)
        | User.email.startswith(TEST_CONSENT_EMAIL_PREFIX)
        | User.email.startswith(TEST_MATCHING_EMAIL_PREFIX)
        | User.email.startswith(TEST_OFFER_EMAIL_PREFIX)
        | User.email.startswith(TEST_KFS_EMAIL_PREFIX)
        | User.email.startswith(TEST_SELECT_EMAIL_PREFIX)
        | User.email.startswith(TEST_SUBMISSION_EMAIL_PREFIX)
    )

    test_app_subquery = session.query(LoanApplication.id).filter(
        LoanApplication.customer_id.in_(test_user_subquery)
    )

    test_run_subquery = session.query(MatchRun.id).filter(
        MatchRun.application_id.in_(test_app_subquery)
    )

    # -2. Lender events linked to test submissions
    session.query(LenderEvent).filter(
        LenderEvent.submission_id.in_(
            session.query(OfferSubmission.id).filter(
                OfferSubmission.application_id.in_(test_app_subquery)
            )
        )
    ).delete(synchronize_session=False)

    # -1. Offer submissions linked to test applications
    session.query(OfferSubmission).filter(
        OfferSubmission.application_id.in_(test_app_subquery)
    ).delete(synchronize_session=False)

    # 0. Offers linked to test decisions
    session.query(Offer).filter(
        Offer.lender_decision_id.in_(
            session.query(LenderDecision.id).filter(
                LenderDecision.match_run_id.in_(test_run_subquery)
            )
        )
    ).delete(synchronize_session=False)

    # 1. Lender decisions linked to test match runs
    session.query(LenderDecision).filter(
        LenderDecision.match_run_id.in_(test_run_subquery)
    ).delete(synchronize_session=False)

    # 2. Match runs linked to test applications
    session.query(MatchRun).filter(
        MatchRun.application_id.in_(test_app_subquery)
    ).delete(synchronize_session=False)

    # 3. Consents linked to test applications
    session.query(Consent).filter(
        Consent.application_id.in_(test_app_subquery)
    ).delete(synchronize_session=False)

    # 4. Lead assignments
    session.query(LeadAssignment).filter(
        LeadAssignment.lead_id.in_(
            session.query(Lead.id).filter(
                Lead.synthetic_reference.startswith(TEST_RBAC_REF_PREFIX)
            )
        )
    ).delete(synchronize_session=False)

    session.query(LeadAssignment).filter(
        LeadAssignment.caller_id.in_(test_user_subquery)
    ).delete(synchronize_session=False)

    # 5. Loan applications created by test users or for test leads
    session.query(LoanApplication).filter(
        LoanApplication.customer_id.in_(test_user_subquery)
    ).delete(synchronize_session=False)

    session.query(LoanApplication).filter(
        LoanApplication.lead_id.in_(
            session.query(Lead.id).filter(
                Lead.synthetic_reference.startswith(TEST_RBAC_REF_PREFIX)
            )
        )
    ).delete(synchronize_session=False)

    # 6. Test leads
    session.query(Lead).filter(
        Lead.synthetic_reference.startswith(TEST_RBAC_REF_PREFIX)
    ).delete(synchronize_session=False)

    # 7. Test users
    session.query(User).filter(
        User.email.startswith(TEST_EMAIL_PREFIX)
        | User.email.startswith(TEST_RBAC_EMAIL_PREFIX)
        | User.email.startswith(TEST_APP_EMAIL_PREFIX)
        | User.email.startswith(TEST_CONSENT_EMAIL_PREFIX)
        | User.email.startswith(TEST_MATCHING_EMAIL_PREFIX)
        | User.email.startswith(TEST_OFFER_EMAIL_PREFIX)
        | User.email.startswith(TEST_KFS_EMAIL_PREFIX)
        | User.email.startswith(TEST_SELECT_EMAIL_PREFIX)
        | User.email.startswith(TEST_SUBMISSION_EMAIL_PREFIX)
    ).delete(synchronize_session=False)

    session.commit()


@pytest.fixture(autouse=True)
def cleanup_test_records() -> Generator[None, None, None]:
    """Clean up only records created by test suites without truncating tables."""
    yield
    with SessionLocal() as session:
        _clean_all_test_records(session)


def create_fictional_user(
    db: Session,
    email: str,
    role: str,
    full_name: str,
) -> Tuple[User, str]:
    """Helper to create a test user with a hashed password and return (User, JWT)."""
    hashed_pw = hash_password("DummyTestingPassword123!")
    user = User(
        full_name=full_name,
        email=email,
        password_hash=hashed_pw,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.id)
    return user, token


@pytest.fixture
def rbac_customer(db_session: Session) -> Tuple[User, str]:
    """Create a test customer user and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_RBAC_EMAIL_PREFIX}customer@example.com",
        "customer",
        "Test RBAC Customer",
    )


@pytest.fixture
def rbac_caller_a(db_session: Session) -> Tuple[User, str]:
    """Create test caller A and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_RBAC_EMAIL_PREFIX}caller_a@example.com",
        "caller",
        "Test RBAC Caller A",
    )


@pytest.fixture
def rbac_caller_b(db_session: Session) -> Tuple[User, str]:
    """Create test caller B and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_RBAC_EMAIL_PREFIX}caller_b@example.com",
        "caller",
        "Test RBAC Caller B",
    )


@pytest.fixture
def rbac_admin(db_session: Session) -> Tuple[User, str]:
    """Create test admin and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_RBAC_EMAIL_PREFIX}admin@example.com",
        "admin",
        "Test RBAC Admin",
    )


@pytest.fixture
def rbac_unassigned_caller(db_session: Session) -> Tuple[User, str]:
    """Create test caller with no leads assigned and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_RBAC_EMAIL_PREFIX}unassigned_caller@example.com",
        "caller",
        "Test RBAC Unassigned Caller",
    )


@pytest.fixture
def app_customer_a(db_session: Session) -> Tuple[User, str]:
    """Create test customer A for application tests and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_APP_EMAIL_PREFIX}customer_a@example.com",
        "customer",
        "Test Application Customer A",
    )


@pytest.fixture
def app_customer_b(db_session: Session) -> Tuple[User, str]:
    """Create test customer B for application tests and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_APP_EMAIL_PREFIX}customer_b@example.com",
        "customer",
        "Test Application Customer B",
    )


@pytest.fixture
def consent_customer_a(db_session: Session) -> Tuple[User, str]:
    """Create test customer A for consent tests and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_CONSENT_EMAIL_PREFIX}customer_a@example.com",
        "customer",
        "Test Consent Customer A",
    )


@pytest.fixture
def consent_customer_b(db_session: Session) -> Tuple[User, str]:
    """Create test customer B for consent tests and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_CONSENT_EMAIL_PREFIX}customer_b@example.com",
        "customer",
        "Test Consent Customer B",
    )


@pytest.fixture
def offer_customer_a(db_session: Session) -> Tuple[User, str]:
    """Create test customer A for offer tests and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_OFFER_EMAIL_PREFIX}customer_a@example.com",
        "customer",
        "Test Offer Customer A",
    )


@pytest.fixture
def offer_customer_b(db_session: Session) -> Tuple[User, str]:
    """Create test customer B for offer tests and return (User, token)."""
    return create_fictional_user(
        db_session,
        f"{TEST_OFFER_EMAIL_PREFIX}customer_b@example.com",
        "customer",
        "Test Offer Customer B",
    )


def create_fictional_lead_with_assignment(
    db: Session,
    ref: str,
    applicant_name: str,
    caller_id: int,
    amount: Decimal = Decimal("50000.00"),
) -> Lead:
    """Helper to create a test lead and assign it to a caller."""
    lead = Lead(
        synthetic_reference=ref,
        applicant_name=applicant_name,
        age=32,
        monthly_income=Decimal("45000.00"),
        work_type="salaried",
        requested_amount=amount,
        status="new",
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
