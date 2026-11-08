from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Generator, List, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.models.lender_decision import LenderDecision
from app.models.lender_policy import LenderPolicy
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.models.user import User
from app.services.consent_notices import (
    PURPOSE_ELIGIBILITY_MATCHING,
    PURPOSE_SHARING_WITH_MOCK_LENDERS,
)
from app.services.matching_service import run_matching
from app.services.offer_service import (
    MOCK_KFS_AMORTIZATION_METHOD,
    MOCK_KFS_CALCULATION_DISCLOSURE,
    MOCK_KFS_DOCUMENT_TYPE,
    MOCK_KFS_DOCUMENT_VERSION,
    MOCK_KFS_FEE_DISCLOSURE,
    MOCK_KFS_PAYMENT_FREQUENCY,
    MOCK_KFS_TRAINING_DISCLOSURE,
    generate_application_offers,
)
from tests.conftest import create_fictional_user

TEST_KFS_PREFIX = "pytest_kfs_"

CANONICAL_TEST_POLICIES = [
    {
        "lender_code": "APEX_FINANCIAL",
        "lender_name": "Apex Financial",
        "policy_version": "v1.0",
        "is_active": True,
        "rules": {
            "min_age": 21,
            "min_monthly_income": "25000.00",
            "allowed_work_types": ["salaried", "self_employed"],
        },
        "offer_terms": {
            "apr_percent": "18.0000",
            "term_months": 24,
            "max_loan_amount": "250000.00",
        },
    },
    {
        "lender_code": "HORIZON_CREDIT",
        "lender_name": "Horizon Credit",
        "policy_version": "v1.0",
        "is_active": True,
        "rules": {
            "min_age": 23,
            "min_monthly_income": "30000.00",
            "allowed_work_types": ["salaried"],
        },
        "offer_terms": {
            "apr_percent": "16.0000",
            "term_months": 36,
            "max_loan_amount": "300000.00",
        },
    },
    {
        "lender_code": "STERLING_LOANS",
        "lender_name": "Sterling Loans",
        "policy_version": "v1.0",
        "is_active": True,
        "rules": {
            "min_age": 25,
            "min_monthly_income": "40000.00",
            "allowed_work_types": ["salaried", "self_employed"],
        },
        "offer_terms": {
            "apr_percent": "20.0000",
            "term_months": 18,
            "max_loan_amount": "150000.00",
        },
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kfs_customer_a(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer A."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_KFS_PREFIX}customer_a@example.com",
        role="customer",
        full_name="KFS Customer A",
    )


@pytest.fixture
def kfs_customer_b(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer B."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_KFS_PREFIX}customer_b@example.com",
        role="customer",
        full_name="KFS Customer B",
    )


@pytest.fixture
def kfs_caller(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Caller."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_KFS_PREFIX}caller@example.com",
        role="caller",
        full_name="KFS Test Caller",
    )


@pytest.fixture
def kfs_admin(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Admin."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_KFS_PREFIX}admin@example.com",
        role="admin",
        full_name="KFS Test Admin",
    )


def _clean_kfs_test_records(db: Session) -> None:
    """Safely delete test records belonging only to kfs test applications and users."""
    kfs_user_ids = [
        u[0]
        for u in db.query(User.id)
        .filter(User.email.startswith(TEST_KFS_PREFIX))
        .all()
    ]
    if kfs_user_ids:
        app_ids = [
            a[0]
            for a in db.query(LoanApplication.id)
            .filter(LoanApplication.customer_id.in_(kfs_user_ids))
            .all()
        ]
        if app_ids:
            run_ids = [
                r[0]
                for r in db.query(MatchRun.id)
                .filter(MatchRun.application_id.in_(app_ids))
                .all()
            ]
            if run_ids:
                dec_ids = [
                    d[0]
                    for d in db.query(LenderDecision.id)
                    .filter(LenderDecision.match_run_id.in_(run_ids))
                    .all()
                ]
                if dec_ids:
                    db.query(Offer).filter(
                        Offer.lender_decision_id.in_(dec_ids)
                    ).delete(synchronize_session=False)

                    db.query(LenderDecision).filter(
                        LenderDecision.id.in_(dec_ids)
                    ).delete(synchronize_session=False)

                db.query(MatchRun).filter(
                    MatchRun.id.in_(run_ids)
                ).delete(synchronize_session=False)

            db.query(Consent).filter(
                Consent.application_id.in_(app_ids)
            ).delete(synchronize_session=False)

            db.query(LoanApplication).filter(
                LoanApplication.id.in_(app_ids)
            ).delete(synchronize_session=False)

    db.commit()


@pytest.fixture
def setup_kfs_policies(db_session: Session) -> Generator[None, None, None]:
    """Ensure canonical test policies exist in isolated test database with canonical terms."""
    _clean_kfs_test_records(db_session)

    for config in CANONICAL_TEST_POLICIES:
        p = (
            db_session.query(LenderPolicy)
            .filter(
                LenderPolicy.lender_code == config["lender_code"],
                LenderPolicy.policy_version == config["policy_version"],
            )
            .first()
        )
        if p is None:
            p = LenderPolicy(**config)
            db_session.add(p)
        else:
            p.lender_name = config["lender_name"]
            p.is_active = config["is_active"]
            p.rules = config["rules"]
            p.offer_terms = config["offer_terms"]

    db_session.commit()

    yield

    _clean_kfs_test_records(db_session)

    for config in CANONICAL_TEST_POLICIES:
        p = (
            db_session.query(LenderPolicy)
            .filter(
                LenderPolicy.lender_code == config["lender_code"],
                LenderPolicy.policy_version == config["policy_version"],
            )
            .first()
        )
        if p is not None:
            p.lender_name = config["lender_name"]
            p.is_active = config["is_active"]
            p.rules = config["rules"]
            p.offer_terms = config["offer_terms"]
    db_session.commit()


def _create_matched_app_with_offers(
    db: Session,
    customer_id: int,
    requested_amount: Decimal = Decimal("200000.00"),
    age: int = 26,
    work_type: str = "salaried",
) -> Tuple[LoanApplication, MatchRun, List[Offer]]:
    """Helper to create an application, grant consents, run matching, and generate offers."""
    app = LoanApplication(
        customer_id=customer_id,
        age=age,
        monthly_income=Decimal("50000.00"),
        work_type=work_type,
        requested_amount=requested_amount,
        status="draft",
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    now = datetime.now(timezone.utc)
    c1 = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="granted",
        granted_at=now,
    )
    c2 = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=now,
    )
    db.add_all([c1, c2])
    db.commit()

    match_run = run_matching(db=db, customer_id=customer_id, application_id=app.id)
    gen_resp = generate_application_offers(db=db, customer_id=customer_id, application_id=app.id)

    offers = (
        db.query(Offer)
        .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
        .filter(LenderDecision.match_run_id == match_run.id)
        .all()
    )
    return app, match_run, offers


# ---------------------------------------------------------------------------
# Test Cases (Requirements 1 to 31)
# ---------------------------------------------------------------------------


def test_authenticated_owner_can_retrieve_mock_kfs(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Cases 1, 2, 3, 4, 5: Customer can retrieve mock KFS; document identification metadata is verified."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    offer = offers[0]

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["document_type"] == MOCK_KFS_DOCUMENT_TYPE
    assert data["document_version"] == MOCK_KFS_DOCUMENT_VERSION
    assert data["mock_kfs_reference"] == offer.mock_kfs_reference
    assert data["offer_id"] == offer.id
    assert data["application_id"] == app.id


def test_lender_information_and_decision_version_snapshot(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Cases 6 & 7: Lender code/name and policy version from decision snapshot are returned."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)

    apex_offer = next(
        o for o in offers if o.lender_decision.lender_policy.lender_code == "APEX_FINANCIAL"
    )

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{apex_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["lender_code"] == "APEX_FINANCIAL"
    assert data["lender_name"] == "Apex Financial"
    assert data["policy_version"] == apex_offer.lender_decision.policy_version_snapshot
    assert data["offer_status"] == "available"
    assert data["valid_until"] is None


def test_kfs_financial_terms_and_amortization_schedule(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Cases 8, 9, 10, 11, 12, 13, 14, 15: Stored financial terms and calculated totals match exact specifications."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)

    for offer in offers:
        response = client.get(
            f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Stored Offer terms
        assert Decimal(data["loan_amount"]) == offer.loan_amount
        assert Decimal(data["nominal_annual_apr_percent"]) == offer.apr
        assert data["term_months"] == offer.term_months
        assert data["number_of_installments"] == offer.term_months
        assert data["payment_frequency"] == MOCK_KFS_PAYMENT_FREQUENCY
        assert Decimal(data["monthly_installment"]) == offer.monthly_installment
        assert data["amortization_method"] == MOCK_KFS_AMORTIZATION_METHOD

        # Calculated totals
        expected_total_repayment = (
            offer.monthly_installment * Decimal(offer.term_months)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_total_interest = (
            expected_total_repayment - offer.loan_amount
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        assert Decimal(data["estimated_total_repayment"]) == expected_total_repayment
        assert Decimal(data["estimated_total_interest"]) == expected_total_interest


def test_kfs_zero_apr_handling(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Case 16: Zero APR offer correctly sets estimated_total_interest=0.00 and repayment=loan_amount."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)

    # Manually configure an offer with 0% APR to test boundary rule
    target_offer = offers[0]
    target_offer.apr = Decimal("0.0000")
    target_offer.monthly_installment = (
        target_offer.loan_amount / Decimal(target_offer.term_months)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    db_session.commit()

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["nominal_annual_apr_percent"]) == Decimal("0.0000")
    assert Decimal(data["estimated_total_interest"]) == Decimal("0.00")
    assert Decimal(data["estimated_total_repayment"]) == target_offer.loan_amount


def test_kfs_decimal_precision_preservation(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Case 17: All financial values maintain exact Decimal formatting and 2 decimal places."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    offer = offers[0]

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    for key in (
        "loan_amount",
        "monthly_installment",
        "estimated_total_repayment",
        "estimated_total_interest",
    ):
        val = data[key]
        assert isinstance(val, str)
        parts = val.split(".")
        assert len(parts) == 2
        assert len(parts[1]) == 2


def test_kfs_disclosures_content(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Cases 18, 19, 20: Fee, calculation, and training disclosures contain exact required text."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    offer = offers[0]

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["fee_disclosure"] == MOCK_KFS_FEE_DISCLOSURE
    assert "Processing fees" in data["fee_disclosure"]
    assert "not modeled" in data["fee_disclosure"]

    assert data["calculation_disclosure"] == MOCK_KFS_CALCULATION_DISCLOSURE
    assert "Monthly installment and repayment totals are illustrative calculations" in data["calculation_disclosure"]
    assert "Final-installment adjustments" in data["calculation_disclosure"]

    assert data["training_disclosure"] == MOCK_KFS_TRAINING_DISCLOSURE
    assert "fictional software-training document only" in data["training_disclosure"]
    assert "No real lender or financial institution is involved." in data["training_disclosure"]


def test_kfs_historical_offer_from_earlier_match_run(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Case 21: Application owner can retrieve KFS for a historical offer from an earlier match run."""
    user, token = kfs_customer_a
    # Run 1: age=22, self_employed (1 offer generated)
    app, run1, offers_run1 = _create_matched_app_with_offers(
        db_session, user.id, age=22, work_type="self_employed"
    )
    assert len(offers_run1) == 1
    old_offer = offers_run1[0]

    # Update app profile and run Match Run 2
    app.age = 26
    app.work_type = "salaried"
    db_session.commit()

    run2 = run_matching(db=db_session, customer_id=user.id, application_id=app.id)
    assert run2.run_number == 2
    generate_application_offers(db=db_session, customer_id=user.id, application_id=app.id)

    # Historical offer from run 1 is still accessible via KFS endpoint
    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{old_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["offer_id"] == old_offer.id
    assert data["mock_kfs_reference"] == old_offer.mock_kfs_reference
    assert data["lender_code"] == "APEX_FINANCIAL"


def test_customer_cannot_retrieve_another_customer_offer(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
    kfs_customer_b: Tuple[User, str],
) -> None:
    """Case 22: Customer B cannot retrieve customer A's offer KFS (returns 404)."""
    user_a, _ = kfs_customer_a
    user_b, token_b = kfs_customer_b

    app_a, run_a, offers_a = _create_matched_app_with_offers(db_session, user_a.id)
    offer_a = offers_a[0]

    response = client.get(
        f"/api/v1/applications/{app_a.id}/offers/{offer_a.id}/kfs",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Loan application not found."


def test_customer_cannot_retrieve_offer_of_different_application(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Case 23: Customer cannot retrieve an offer ID associated with another of their own applications."""
    user, token = kfs_customer_a
    app_1, _, offers_1 = _create_matched_app_with_offers(db_session, user.id)
    app_2, _, _ = _create_matched_app_with_offers(db_session, user.id)

    offer_1 = offers_1[0]

    # Attempt to query offer_1 under app_2
    response = client.get(
        f"/api/v1/applications/{app_2.id}/offers/{offer_1.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Offer not found."


def test_unknown_offer_id_returns_404(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Case 24: Unknown offer ID returns 404."""
    user, token = kfs_customer_a
    app, _, _ = _create_matched_app_with_offers(db_session, user.id)

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/999999/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Offer not found."


def test_unknown_application_id_returns_404(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Case 25: Unknown application ID returns 404."""
    user, token = kfs_customer_a

    response = client.get(
        f"/api/v1/applications/999999/offers/1/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Loan application not found."


def test_missing_authentication_returns_401(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Case 26: Missing authorization header returns 401."""
    user, _ = kfs_customer_a
    app, _, offers = _create_matched_app_with_offers(db_session, user.id)
    offer = offers[0]

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs"
    )
    assert response.status_code == 401


def test_caller_and_admin_cannot_access_kfs_endpoint(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
    kfs_caller: Tuple[User, str],
    kfs_admin: Tuple[User, str],
) -> None:
    """Cases 27 & 28: Non-customer roles receive 403 Forbidden on the KFS endpoint."""
    user, _ = kfs_customer_a
    _, caller_token = kfs_caller
    _, admin_token = kfs_admin

    app, _, offers = _create_matched_app_with_offers(db_session, user.id)
    offer = offers[0]

    for token in (caller_token, admin_token):
        response = client.get(
            f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


def test_reading_kfs_preserves_offer_and_creates_no_duplicates(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Cases 29, 30, 31: KFS retrieval is strictly read-only; does not mutate Offer, MatchRun, or LenderDecision."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    offer = offers[0]

    orig_loan_amount = offer.loan_amount
    orig_apr = offer.apr
    orig_term_months = offer.term_months
    orig_emi = offer.monthly_installment
    orig_status = offer.status
    orig_created_at = offer.created_at

    offer_count_before = db_session.query(Offer).count()
    run_count_before = db_session.query(MatchRun).count()
    dec_count_before = db_session.query(LenderDecision).count()

    # Call KFS endpoint multiple times
    for _ in range(3):
        response = client.get(
            f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    # Refresh offer from DB and verify immutability
    db_session.refresh(offer)
    assert offer.loan_amount == orig_loan_amount
    assert offer.apr == orig_apr
    assert offer.term_months == orig_term_months
    assert offer.monthly_installment == orig_emi
    assert offer.status == orig_status
    assert offer.created_at == orig_created_at

    # Verify zero additional records created
    assert db_session.query(Offer).count() == offer_count_before
    assert db_session.query(MatchRun).count() == run_count_before
    assert db_session.query(LenderDecision).count() == dec_count_before


def test_kfs_low_positive_apr_rounding_regression(
    client: TestClient,
    db_session: Session,
    setup_kfs_policies: None,
    kfs_customer_a: Tuple[User, str],
) -> None:
    """Part B regression: Low-positive-APR with cent rounding floors repayment at principal, preventing negative interest."""
    user, token = kfs_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)

    # Configure the exact boundary condition from Part B:
    # Principal = 1000.90, APR = 0.0001, Tenure = 360, EMI = 2.78
    target_offer = offers[0]
    target_offer.loan_amount = Decimal("1000.90")
    target_offer.apr = Decimal("0.0001")
    target_offer.term_months = 360
    target_offer.monthly_installment = Decimal("2.78")
    db_session.commit()

    response = client.get(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["loan_amount"]) == Decimal("1000.90")
    assert Decimal(data["monthly_installment"]) == Decimal("2.78")
    assert data["term_months"] == 360
    # 2.78 * 360 = 1000.80 < 1000.90, so repayment is floored at 1000.90 and interest is 0.00
    assert Decimal(data["estimated_total_repayment"]) == Decimal("1000.90")
    assert Decimal(data["estimated_total_interest"]) == Decimal("0.00")

