from datetime import datetime, timezone
from decimal import Decimal
from typing import Generator, Tuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from app.services.offer_calculator import (
    calculate_monthly_installment,
    calculate_offer_amount,
)
from tests.conftest import create_fictional_user

TEST_OFFER_LENDER_CODES = [
    "APEX_FINANCIAL",
    "HORIZON_CREDIT",
    "STERLING_LOANS",
    "CUSTOM_TEST_LENDER",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def offer_caller(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Caller."""
    return create_fictional_user(
        db_session,
        email="pytest_offer_caller@example.com",
        role="caller",
        full_name="Offer Test Caller",
    )


@pytest.fixture
def offer_admin(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Admin."""
    return create_fictional_user(
        db_session,
        email="pytest_offer_admin@example.com",
        role="admin",
        full_name="Offer Test Admin",
    )


def _clean_offer_test_policies(db: Session) -> None:
    """Safely delete test records in foreign-key safe order."""
    offer_user_ids = [
        u[0]
        for u in db.query(User.id)
        .filter(User.email.startswith("pytest_offer_"))
        .all()
    ]
    if offer_user_ids:
        app_ids = [
            a[0]
            for a in db.query(LoanApplication.id)
            .filter(LoanApplication.customer_id.in_(offer_user_ids))
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
                    LenderDecision.match_run_id.in_(run_ids)
                ).delete(synchronize_session=False)

                db.query(MatchRun).filter(
                    MatchRun.id.in_(run_ids)
                ).delete(synchronize_session=False)

            db.query(Consent).filter(
                Consent.application_id.in_(app_ids)
            ).delete(synchronize_session=False)

            db.query(LoanApplication).filter(
                LoanApplication.customer_id.in_(offer_user_ids)
            ).delete(synchronize_session=False)

    test_policies = (
        db.query(LenderPolicy.id)
        .filter(LenderPolicy.lender_code.in_(TEST_OFFER_LENDER_CODES))
        .all()
    )
    if test_policies:
        p_ids = [p[0] for p in test_policies]
        policy_dec_ids = [
            d[0]
            for d in db.query(LenderDecision.id)
            .filter(LenderDecision.lender_policy_id.in_(p_ids))
            .all()
        ]
        if policy_dec_ids:
            db.query(Offer).filter(
                Offer.lender_decision_id.in_(policy_dec_ids)
            ).delete(synchronize_session=False)

        db.query(LenderDecision).filter(
            LenderDecision.lender_policy_id.in_(p_ids)
        ).delete(synchronize_session=False)

        db.query(LenderPolicy).filter(
            LenderPolicy.id.in_(p_ids)
        ).delete(synchronize_session=False)

    db.commit()


@pytest.fixture
def setup_offer_policies(db_session: Session) -> Generator[None, None, None]:
    """Insert three canonical test policies into isolated test database."""
    _clean_offer_test_policies(db_session)

    policies = [
        LenderPolicy(
            lender_code="APEX_FINANCIAL",
            lender_name="Apex Financial",
            policy_version="v1.0",
            is_active=True,
            rules={
                "min_age": 21,
                "min_monthly_income": "25000.00",
                "allowed_work_types": ["salaried", "self_employed"],
            },
            offer_terms={
                "apr_percent": "18.0000",
                "term_months": 24,
                "max_loan_amount": "250000.00",
            },
        ),
        LenderPolicy(
            lender_code="HORIZON_CREDIT",
            lender_name="Horizon Credit",
            policy_version="v1.0",
            is_active=True,
            rules={
                "min_age": 23,
                "min_monthly_income": "30000.00",
                "allowed_work_types": ["salaried"],
            },
            offer_terms={
                "apr_percent": "16.0000",
                "term_months": 36,
                "max_loan_amount": "300000.00",
            },
        ),
        LenderPolicy(
            lender_code="STERLING_LOANS",
            lender_name="Sterling Loans",
            policy_version="v1.0",
            is_active=True,
            rules={
                "min_age": 25,
                "min_monthly_income": "40000.00",
                "allowed_work_types": ["salaried", "self_employed"],
            },
            offer_terms={
                "apr_percent": "20.0000",
                "term_months": 18,
                "max_loan_amount": "150000.00",
            },
        ),
    ]
    db_session.add_all(policies)
    db_session.commit()

    yield

    _clean_offer_test_policies(db_session)


def _create_app_with_consents(
    db: Session,
    customer_id: int,
    age: int = 26,
    monthly_income: Decimal = Decimal("50000.00"),
    work_type: str = "salaried",
    requested_amount: Decimal = Decimal("200000.00"),
    grant_eligibility: bool = True,
    grant_sharing: bool = True,
    eligibility_version: str = "v1.0",
    sharing_version: str = "v1.0",
    eligibility_status: str = "granted",
    sharing_status: str = "granted",
    app_status: str = "draft",
) -> LoanApplication:
    """Helper to create a loan application and associated consent records."""
    app = LoanApplication(
        customer_id=customer_id,
        age=age,
        monthly_income=monthly_income,
        work_type=work_type,
        requested_amount=requested_amount,
        status=app_status,
        lead_id=None,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    now = datetime.now(timezone.utc)
    if grant_eligibility:
        c1 = Consent(
            application_id=app.id,
            purpose=PURPOSE_ELIGIBILITY_MATCHING,
            notice_version=eligibility_version,
            status=eligibility_status,
            granted_at=now if eligibility_status == "granted" else None,
            revoked_at=now if eligibility_status == "revoked" else None,
        )
        db.add(c1)

    if grant_sharing:
        c2 = Consent(
            application_id=app.id,
            purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
            notice_version=sharing_version,
            status=sharing_status,
            granted_at=now if sharing_status == "granted" else None,
            revoked_at=now if sharing_status == "revoked" else None,
        )
        db.add(c2)

    db.commit()
    db.refresh(app)
    return app


def _create_matched_application(
    db: Session,
    customer_id: int,
    age: int = 26,
    monthly_income: Decimal = Decimal("50000.00"),
    work_type: str = "salaried",
    requested_amount: Decimal = Decimal("200000.00"),
) -> Tuple[LoanApplication, MatchRun]:
    """Helper to create an application, grant consents, and run matching successfully."""
    app = _create_app_with_consents(
        db=db,
        customer_id=customer_id,
        age=age,
        monthly_income=monthly_income,
        work_type=work_type,
        requested_amount=requested_amount,
    )
    match_run = run_matching(db=db, customer_id=customer_id, application_id=app.id)
    return app, match_run


# ---------------------------------------------------------------------------
# Test Cases (Covering Requirements 1 to 30 + DB Unique Constraint)
# ---------------------------------------------------------------------------


def test_customer_can_generate_offers_after_matching(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 1: Customer can generate offers after successful matching."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["application_id"] == app.id
    assert data["match_run_id"] == run.id
    assert data["run_number"] == 1
    assert data["generated_count"] == 3
    assert len(data["offers"]) == 3


def test_one_offer_per_eligible_decision_and_ineligible_receive_none(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Cases 2 & 3: Exactly one offer per eligible decision; ineligible decisions receive no offer."""
    user, token = offer_customer_a
    # age=22, work_type='self_employed': Apex eligible (min_age 21), Horizon ineligible (work_type, age), Sterling ineligible (age 25)
    app, run = _create_matched_application(
        db_session,
        user.id,
        age=22,
        monthly_income=Decimal("50000.00"),
        work_type="self_employed",
        requested_amount=Decimal("100000.00"),
    )

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["generated_count"] == 1
    assert len(data["offers"]) == 1
    assert data["offers"][0]["lender_code"] == "APEX_FINANCIAL"

    # Verify directly in DB that ineligible decisions have no offer
    ineligible_decisions = (
        db_session.query(LenderDecision)
        .filter(
            LenderDecision.match_run_id == run.id,
            LenderDecision.decision_status == "ineligible",
        )
        .all()
    )
    assert len(ineligible_decisions) == 2
    for d in ineligible_decisions:
        offer_exists = (
            db_session.query(Offer).filter(Offer.lender_decision_id == d.id).first()
        )
        assert offer_exists is None


def test_offer_amount_calculation_and_cap(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 4: Offer amount equals min(requested_amount, lender max_loan_amount)."""
    user, token = offer_customer_a
    # Requested amount = 200,000.
    # Apex max = 250,000 -> 200,000
    # Horizon max = 300,000 -> 200,000
    # Sterling max = 150,000 -> 150,000 (capped!)
    app, run = _create_matched_application(
        db_session,
        user.id,
        requested_amount=Decimal("200000.00"),
    )

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    offers = {o["lender_code"]: o for o in response.json()["offers"]}

    assert Decimal(offers["APEX_FINANCIAL"]["loan_amount"]) == Decimal("200000.00")
    assert Decimal(offers["HORIZON_CREDIT"]["loan_amount"]) == Decimal("200000.00")
    assert Decimal(offers["STERLING_LOANS"]["loan_amount"]) == Decimal("150000.00")


def test_offer_financial_terms_and_emi(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Cases 5, 6, 7: APR, tenure, and EMI are correctly computed and saved."""
    user, token = offer_customer_a
    app, run = _create_matched_application(
        db_session,
        user.id,
        requested_amount=Decimal("200000.00"),
    )

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    offers = {o["lender_code"]: o for o in response.json()["offers"]}

    # Apex: 200,000, 18%, 24 months
    apex = offers["APEX_FINANCIAL"]
    assert Decimal(apex["apr"]) == Decimal("18.0000")
    assert apex["term_months"] == 24
    expected_apex_emi = calculate_monthly_installment(
        Decimal("200000.00"), Decimal("18.0000"), 24
    )
    assert Decimal(apex["monthly_installment"]) == expected_apex_emi

    # Horizon: 200,000, 16%, 36 months
    horizon = offers["HORIZON_CREDIT"]
    assert Decimal(horizon["apr"]) == Decimal("16.0000")
    assert horizon["term_months"] == 36
    expected_horizon_emi = calculate_monthly_installment(
        Decimal("200000.00"), Decimal("16.0000"), 36
    )
    assert Decimal(horizon["monthly_installment"]) == expected_horizon_emi

    # Sterling: 150,000, 20%, 18 months
    sterling = offers["STERLING_LOANS"]
    assert Decimal(sterling["apr"]) == Decimal("20.0000")
    assert sterling["term_months"] == 18
    expected_sterling_emi = calculate_monthly_installment(
        Decimal("150000.00"), Decimal("20.0000"), 18
    )
    assert Decimal(sterling["monthly_installment"]) == expected_sterling_emi


def test_offer_status_kfs_reference_and_valid_until(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Cases 8, 9, 10: Status is 'available', mock KFS reference has documented format, valid_until is None."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    for offer in response.json()["offers"]:
        assert offer["status"] == "available"
        assert offer["mock_kfs_reference"] == f"TRAINING-MOCK-KFS-D{offer['lender_decision_id']}"
        assert offer["valid_until"] is None


def test_repeated_generation_idempotency(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Cases 11 & 12: Repeated generation is idempotent, does not duplicate, and does not alter terms."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    # First call
    resp1 = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["generated_count"] == 3

    # Second call
    resp2 = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["generated_count"] == 0  # 0 new offers generated
    assert len(data2["offers"]) == 3

    # Compare offer attributes
    for o1, o2 in zip(data1["offers"], data2["offers"]):
        assert o1["id"] == o2["id"]
        assert o1["lender_decision_id"] == o2["lender_decision_id"]
        assert o1["loan_amount"] == o2["loan_amount"]
        assert o1["apr"] == o2["apr"]
        assert o1["term_months"] == o2["term_months"]
        assert o1["monthly_installment"] == o2["monthly_installment"]
        assert o1["status"] == o2["status"]
        assert o1["created_at"] == o2["created_at"]

    # Verify database count
    total_offers = (
        db_session.query(Offer)
        .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
        .filter(LenderDecision.match_run_id == run.id)
        .count()
    )
    assert total_offers == 3


def test_only_latest_completed_match_run_used_and_old_offers_preserved(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Cases 13 & 14: Only latest completed match run is used; older match run offers remain stored."""
    user, token = offer_customer_a
    app, run1 = _create_matched_application(db_session, user.id, age=22, work_type="self_employed")

    # Generate offers for run 1 (1 eligible decision)
    resp1 = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["match_run_id"] == run1.id
    assert data1["run_number"] == 1
    assert data1["generated_count"] == 1
    run1_offer_id = data1["offers"][0]["id"]

    # Now change applicant profile or run matching again (e.g. age 26, salaried)
    app.age = 26
    app.work_type = "salaried"
    db_session.commit()

    run2 = run_matching(db=db_session, customer_id=user.id, application_id=app.id)
    assert run2.run_number == 2

    # Generate offers for run 2 (all 3 eligible)
    resp2 = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["match_run_id"] == run2.id
    assert data2["run_number"] == 2
    assert data2["generated_count"] == 3
    run2_offer_ids = [o["id"] for o in data2["offers"]]

    # Verify old offer from run 1 is still preserved in DB
    old_offer = db_session.query(Offer).filter(Offer.id == run1_offer_id).first()
    assert old_offer is not None
    assert old_offer.id not in run2_offer_ids


def test_get_offers_returns_only_latest_run_offers(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 15: GET offers returns only offers belonging to the latest completed match run."""
    user, token = offer_customer_a
    app, run1 = _create_matched_application(db_session, user.id, age=22, work_type="self_employed")
    client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Run match 2
    app.age = 26
    app.work_type = "salaried"
    db_session.commit()
    run2 = run_matching(db=db_session, customer_id=user.id, application_id=app.id)

    # Generate offers for match 2
    client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )

    # GET offers
    resp = client.get(
        f"/api/v1/applications/{app.id}/offers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    offers = resp.json()
    assert len(offers) == 3

    # Ensure all returned offers belong to run2 decisions
    run2_dec_ids = {
        d.id
        for d in db_session.query(LenderDecision)
        .filter(LenderDecision.match_run_id == run2.id)
        .all()
    }
    for o in offers:
        assert o["lender_decision_id"] in run2_dec_ids


def test_get_offers_returns_empty_list_when_no_match_run(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 16: GET offers returns empty list when no match run exists."""
    user, token = offer_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.get(
        f"/api/v1/applications/{app.id}/offers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_customer_cannot_generate_or_view_another_customer_offers(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
    offer_customer_b: Tuple[User, str],
) -> None:
    """Cases 17 & 18: Customer cannot generate or view another customer's offers (404)."""
    user_a, token_a = offer_customer_a
    user_b, token_b = offer_customer_b

    app_a, run_a = _create_matched_application(db_session, user_a.id)

    # Customer B attempts to generate offers on customer A's application
    resp_gen = client.post(
        f"/api/v1/applications/{app_a.id}/offers/generate",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_gen.status_code == 404
    assert resp_gen.json()["detail"] == "Loan application not found."

    # First customer A generates offers
    client.post(
        f"/api/v1/applications/{app_a.id}/offers/generate",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Customer B attempts to view customer A's offers
    resp_view = client.get(
        f"/api/v1/applications/{app_a.id}/offers",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_view.status_code == 404
    assert resp_view.json()["detail"] == "Loan application not found."


def test_non_customer_roles_cannot_access_offer_endpoints(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
    offer_caller: Tuple[User, str],
    offer_admin: Tuple[User, str],
) -> None:
    """Case 19: Non-customer roles receive 403 on offer endpoints."""
    user_a, token_a = offer_customer_a
    _, caller_token = offer_caller
    _, admin_token = offer_admin

    app, run = _create_matched_application(db_session, user_a.id)

    for token in (caller_token, admin_token):
        resp_post = client.post(
            f"/api/v1/applications/{app.id}/offers/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_post.status_code == 403

        resp_get = client.get(
            f"/api/v1/applications/{app.id}/offers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_get.status_code == 403


def test_missing_consent_prevents_offer_generation(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 20: Missing consent prevents offer generation (409 Conflict)."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    # Delete one mandatory consent
    db_session.query(Consent).filter(
        Consent.application_id == app.id,
        Consent.purpose == PURPOSE_SHARING_WITH_MOCK_LENDERS,
    ).delete()
    db_session.commit()

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    data = resp.json()["detail"]
    assert PURPOSE_SHARING_WITH_MOCK_LENDERS in data["missing_purposes"]


def test_revoked_or_outdated_consent_prevents_offer_generation(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 21: Revoked or outdated consent prevents offer generation (409 Conflict)."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    consent = (
        db_session.query(Consent)
        .filter(
            Consent.application_id == app.id,
            Consent.purpose == PURPOSE_SHARING_WITH_MOCK_LENDERS,
        )
        .first()
    )
    assert consent is not None

    # Test revoked
    consent.status = "revoked"
    db_session.commit()

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409

    # Test outdated version
    consent.status = "granted"
    consent.notice_version = "v0.9"
    db_session.commit()

    resp_outdated = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_outdated.status_code == 409


def test_non_matched_status_prevents_generation(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Status check: Application not in 'matched' status raises 409 Conflict."""
    user, token = offer_customer_a
    app = _create_app_with_consents(db_session, user.id, app_status="draft")

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert "status is 'matched'" in resp.json()["detail"]


def test_no_completed_match_run_prevents_generation(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 22: Application has status 'matched' but no match run exists in DB."""
    user, token = offer_customer_a
    app = _create_app_with_consents(db_session, user.id, app_status="matched")

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert "No match run found" in resp.json()["detail"]


def test_latest_failed_or_incomplete_run_prevents_generation(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 23: Latest match run is incomplete/failed -> 409 Conflict."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    # Test incomplete ('started')
    run.status = "started"
    db_session.commit()

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert "completed match run" in resp.json()["detail"]

    # Test 'failed'
    run.status = "failed"
    db_session.commit()

    resp_failed = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_failed.status_code == 409
    assert "completed match run" in resp_failed.json()["detail"]


def test_missing_offer_terms_produces_configuration_error(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 24: Missing offer_terms on active policy returns 503."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    # Set offer_terms to None on Apex policy
    apex = (
        db_session.query(LenderPolicy)
        .filter(LenderPolicy.lender_code == "APEX_FINANCIAL")
        .first()
    )
    assert apex is not None
    apex.offer_terms = None
    db_session.commit()

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert "missing required 'offer_terms'" in resp.json()["detail"]


def test_malformed_offer_terms_produces_configuration_error(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 25: Malformed offer_terms produces 503."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    apex = (
        db_session.query(LenderPolicy)
        .filter(LenderPolicy.lender_code == "APEX_FINANCIAL")
        .first()
    )
    assert apex is not None
    apex.offer_terms = {"apr_percent": "not-a-number"}
    db_session.commit()

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert "failed validation" in resp.json()["detail"]


def test_policy_version_snapshot_mismatch_produces_configuration_error(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 26: Policy version snapshot mismatch produces 503."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    decision = (
        db_session.query(LenderDecision)
        .filter(LenderDecision.match_run_id == run.id)
        .first()
    )
    assert decision is not None
    decision.policy_version_snapshot = "v2.0-modified"
    db_session.commit()

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert "Policy version mismatch" in resp.json()["detail"]


def test_configuration_failure_does_not_persist_partial_offers(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 27: Configuration error on any lender prevents partial offer generation."""
    user, token = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    # Corrupt Horizon Credit's offer_terms while Apex is valid
    horizon = (
        db_session.query(LenderPolicy)
        .filter(LenderPolicy.lender_code == "HORIZON_CREDIT")
        .first()
    )
    assert horizon is not None
    horizon.offer_terms = None
    db_session.commit()

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503

    # Verify zero offers were persisted in DB
    persisted_count = (
        db_session.query(Offer)
        .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
        .filter(LenderDecision.match_run_id == run.id)
        .count()
    )
    assert persisted_count == 0


def test_zero_eligible_decisions_returns_empty_successful_response(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 28: Zero eligible decisions returns 200 with generated_count=0 and offers=[]."""
    user, token = offer_customer_a
    # Age 18 makes all 3 lenders ineligible
    app, run = _create_matched_application(
        db_session,
        user.id,
        age=18,
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated_count"] == 0
    assert data["offers"] == []


def test_decimal_values_remain_accurate(
    client: TestClient,
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 29: Decimal values maintain precision in responses and database."""
    user, token = offer_customer_a
    app, run = _create_matched_application(
        db_session,
        user.id,
        requested_amount=Decimal("123456.78"),
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    offers = {o["lender_code"]: o for o in resp.json()["offers"]}

    apex = offers["APEX_FINANCIAL"]
    assert apex["loan_amount"] == "123456.78"
    assert apex["apr"] == "18.0000"
    # Ensure monthly_installment has exact 2 decimal places format
    assert len(apex["monthly_installment"].split(".")[1]) == 2


def test_database_unique_constraint_prevents_duplicate_offers(
    db_session: Session,
    setup_offer_policies: None,
    offer_customer_a: Tuple[User, str],
) -> None:
    """Case 31: Database unique constraint on lender_decision_id rejects duplicates."""
    user, _ = offer_customer_a
    app, run = _create_matched_application(db_session, user.id)

    decision = (
        db_session.query(LenderDecision)
        .filter(
            LenderDecision.match_run_id == run.id,
            LenderDecision.decision_status == "eligible",
        )
        .first()
    )
    assert decision is not None

    offer1 = Offer(
        lender_decision_id=decision.id,
        loan_amount=Decimal("100000.00"),
        apr=Decimal("15.0000"),
        term_months=12,
        monthly_installment=Decimal("9000.00"),
        mock_kfs_reference=f"TRAINING-MOCK-KFS-D{decision.id}",
        status="available",
    )
    db_session.add(offer1)
    db_session.commit()

    # Attempt to insert second offer for the same lender_decision_id
    offer2 = Offer(
        lender_decision_id=decision.id,
        loan_amount=Decimal("100000.00"),
        apr=Decimal("15.0000"),
        term_months=12,
        monthly_installment=Decimal("9000.00"),
        mock_kfs_reference=f"TRAINING-MOCK-KFS-D{decision.id}-dup",
        status="available",
    )
    db_session.add(offer2)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
