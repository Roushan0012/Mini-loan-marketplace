from datetime import datetime, timezone
from decimal import Decimal
from typing import Generator, Tuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
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
from tests.conftest import create_fictional_user

TEST_LENDER_CODES = ["APEX_FINANCIAL", "HORIZON_CREDIT", "STERLING_LOANS", "CORRUPT_LENDER"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def matching_customer_a(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer A."""
    return create_fictional_user(
        db_session,
        email="pytest_matching_customer_a@example.com",
        role="customer",
        full_name="Matching Customer A",
    )


@pytest.fixture
def matching_customer_b(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer B."""
    return create_fictional_user(
        db_session,
        email="pytest_matching_customer_b@example.com",
        role="customer",
        full_name="Matching Customer B",
    )


@pytest.fixture
def matching_caller(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Caller."""
    return create_fictional_user(
        db_session,
        email="pytest_matching_caller@example.com",
        role="caller",
        full_name="Matching Caller",
    )


@pytest.fixture
def matching_admin(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Admin."""
    return create_fictional_user(
        db_session,
        email="pytest_matching_admin@example.com",
        role="admin",
        full_name="Matching Admin",
    )


def _clean_test_policies(db: Session) -> None:
    """Safely delete test policies and only decisions/runs belonging to matching test applications."""
    # 1. Identify matching test user IDs
    matching_user_ids = [
        u[0]
        for u in db.query(User.id)
        .filter(User.email.startswith("pytest_matching_"))
        .all()
    ]

    # 2. Identify loan applications owned by matching test users
    matching_app_ids = (
        [
            a[0]
            for a in db.query(LoanApplication.id)
            .filter(LoanApplication.customer_id.in_(matching_user_ids))
            .all()
        ]
        if matching_user_ids
        else []
    )

    # 3. Identify match runs belonging only to matching test applications
    matching_run_ids = (
        [
            r[0]
            for r in db.query(MatchRun.id)
            .filter(MatchRun.application_id.in_(matching_app_ids))
            .all()
        ]
        if matching_app_ids
        else []
    )

    # 4. Delete decisions belonging to these matching test runs
    if matching_run_ids:
        db.query(LenderDecision).filter(
            LenderDecision.match_run_id.in_(matching_run_ids)
        ).delete(synchronize_session=False)

        # 5. Delete only matching test runs
        db.query(MatchRun).filter(
            MatchRun.id.in_(matching_run_ids)
        ).delete(synchronize_session=False)

    # 6. Delete test policies only after checking their test decisions are removed
    test_policies = (
        db.query(LenderPolicy.id)
        .filter(LenderPolicy.lender_code.in_(TEST_LENDER_CODES))
        .all()
    )
    if test_policies:
        p_ids = [p[0] for p in test_policies]
        db.query(LenderDecision).filter(
            LenderDecision.lender_policy_id.in_(p_ids)
        ).delete(synchronize_session=False)

        db.query(LenderPolicy).filter(
            LenderPolicy.id.in_(p_ids)
        ).delete(synchronize_session=False)

    db.commit()


@pytest.fixture
def setup_test_policies(db_session: Session) -> Generator[None, None, None]:
    """Insert three canonical test lender underwriting policies into isolated test database."""
    _clean_test_policies(db_session)

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

    _clean_test_policies(db_session)


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
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    now_utc = datetime.now(timezone.utc)
    if grant_eligibility:
        c1 = Consent(
            application_id=app.id,
            purpose=PURPOSE_ELIGIBILITY_MATCHING,
            notice_version=eligibility_version,
            status=eligibility_status,
            granted_at=now_utc if eligibility_status == "granted" else None,
            revoked_at=now_utc if eligibility_status == "revoked" else None,
        )
        db.add(c1)

    if grant_sharing:
        c2 = Consent(
            application_id=app.id,
            purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
            notice_version=sharing_version,
            status=sharing_status,
            granted_at=now_utc if sharing_status == "granted" else None,
            revoked_at=now_utc if sharing_status == "revoked" else None,
        )
        db.add(c2)

    db.commit()
    db.refresh(app)
    return app


# ---------------------------------------------------------------------------
# 1–5: Authentication & Ownership Tests
# ---------------------------------------------------------------------------


def test_missing_token_returns_401(client: TestClient):
    """1. Missing token returns 401."""
    resp = client.post("/api/v1/applications/1/match")
    assert resp.status_code == 401


def test_caller_cannot_initiate_matching(
    client: TestClient,
    matching_caller: Tuple[User, str],
):
    """2. Caller cannot initiate matching (403)."""
    _, token = matching_caller
    resp = client.post(
        "/api/v1/applications/1/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_admin_cannot_initiate_matching(
    client: TestClient,
    matching_admin: Tuple[User, str],
):
    """3. Admin cannot initiate matching (403)."""
    _, token = matching_admin
    resp = client.post(
        "/api/v1/applications/1/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_customer_cannot_match_another_customer_application(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    matching_customer_b: Tuple[User, str],
):
    """4. Customer cannot match another customer's application (404)."""
    user_a, _ = matching_customer_a
    _, token_b = matching_customer_b
    app_a = _create_app_with_consents(db_session, user_a.id)

    resp = client.post(
        f"/api/v1/applications/{app_a.id}/match",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Loan application not found."


def test_unknown_application_returns_404(
    client: TestClient,
    matching_customer_a: Tuple[User, str],
):
    """5. Unknown application returns 404."""
    _, token_a = matching_customer_a
    resp = client.post(
        "/api/v1/applications/999999/match",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Loan application not found."


# ---------------------------------------------------------------------------
# 6–13: Consent Verification Tests
# ---------------------------------------------------------------------------


def test_no_consents_prevents_matching(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """6. No consents prevents matching (409)."""
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        grant_eligibility=False,
        grant_sharing=False,
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_only_eligibility_consent_prevents_matching(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """7. Only eligibility consent prevents matching (409)."""
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        grant_eligibility=True,
        grant_sharing=False,
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_only_mock_lender_sharing_consent_prevents_matching(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """8. Only mock-lender-sharing consent prevents matching (409)."""
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        grant_eligibility=False,
        grant_sharing=True,
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_revoked_required_consent_prevents_matching(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """9. Revoked required consent prevents matching (409)."""
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        eligibility_status="revoked",
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_outdated_consent_version_prevents_matching(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """10. Outdated consent version prevents matching (409)."""
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        eligibility_version="v0.9",  # Outdated version
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_both_current_active_consents_allow_matching(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """11. Both current active consents allow matching (201)."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["run_number"] == 1
    assert len(data["decisions"]) == 3


def test_missing_purpose_response_identifies_required_consent(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """12. Missing-purpose response identifies which consent is required."""
    user, token = matching_customer_a
    # Grant eligibility matching, leave sharing missing
    app = _create_app_with_consents(
        db_session,
        user.id,
        grant_eligibility=True,
        grant_sharing=False,
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert "sharing_with_mock_lenders" in str(body)


def test_failed_consent_check_creates_no_match_run_or_decisions(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """13. Failed consent check creates no MatchRun or LenderDecision."""
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        grant_eligibility=False,
        grant_sharing=False,
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409

    runs = db_session.query(MatchRun).filter(MatchRun.application_id == app.id).all()
    assert len(runs) == 0

    decisions = (
        db_session.query(LenderDecision)
        .filter(LenderDecision.match_run_id.in_([r.id for r in runs]))
        .all()
    )
    assert len(decisions) == 0


# ---------------------------------------------------------------------------
# 14–24: Policy Evaluation Tests
# ---------------------------------------------------------------------------


def test_all_rules_passing_produces_eligible_decision(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """14. All rules passing produces eligible decision."""
    # Age 30, income 60000, salaried -> passes APEX, HORIZON, and STERLING
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        age=30,
        monthly_income=Decimal("60000.00"),
        work_type="salaried",
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    decisions = resp.json()["decisions"]
    for d in decisions:
        assert d["decision_status"] == "eligible"
        assert d["exclusion_reason_code"] is None
        assert d["exclusion_reason"] is None


def test_age_below_minimum_produces_age_below_minimum(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """15. Age below minimum produces AGE_BELOW_MINIMUM."""
    # Age 22 -> fails HORIZON (min 23) and STERLING (min 25), passes APEX (min 21)
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        age=22,
        monthly_income=Decimal("50000.00"),
        work_type="salaried",
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    d_map = {d["lender_code"]: d for d in resp.json()["decisions"]}
    assert d_map["APEX_FINANCIAL"]["decision_status"] == "eligible"
    assert d_map["HORIZON_CREDIT"]["decision_status"] == "ineligible"
    assert d_map["HORIZON_CREDIT"]["exclusion_reason_code"] == "AGE_BELOW_MINIMUM"
    assert "Applicant age" in d_map["HORIZON_CREDIT"]["exclusion_reason"]


def test_income_below_minimum_produces_income_below_minimum(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """16. Income below minimum produces INCOME_BELOW_MINIMUM."""
    # Age 26, income 28000 -> passes APEX (min 25k), fails HORIZON (min 30k) on income only
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        age=26,
        monthly_income=Decimal("28000.00"),
        work_type="salaried",
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    d_map = {d["lender_code"]: d for d in resp.json()["decisions"]}
    assert d_map["HORIZON_CREDIT"]["decision_status"] == "ineligible"
    assert d_map["HORIZON_CREDIT"]["exclusion_reason_code"] == "INCOME_BELOW_MINIMUM"


def test_work_type_not_permitted_produces_work_type_not_allowed(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """17. Work type not permitted produces WORK_TYPE_NOT_ALLOWED."""
    # Age 26, income 50000, self_employed -> fails HORIZON (allowed=["salaried"]) on work_type only
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        age=26,
        monthly_income=Decimal("50000.00"),
        work_type="self_employed",
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    d_map = {d["lender_code"]: d for d in resp.json()["decisions"]}
    assert d_map["HORIZON_CREDIT"]["decision_status"] == "ineligible"
    assert d_map["HORIZON_CREDIT"]["exclusion_reason_code"] == "WORK_TYPE_NOT_ALLOWED"


def test_multiple_failures_produce_multiple_rules_failed(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """18. Multiple failures produce MULTIPLE_RULES_FAILED and list all failures."""
    # Age 20 (fails min 23), income 10000 (fails min 30000), work_type="other" (fails salaried) for HORIZON
    user, token = matching_customer_a
    app = _create_app_with_consents(
        db_session,
        user.id,
        age=20,
        monthly_income=Decimal("10000.00"),
        work_type="other",
    )

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    d_map = {d["lender_code"]: d for d in resp.json()["decisions"]}
    horizon = d_map["HORIZON_CREDIT"]
    assert horizon["decision_status"] == "ineligible"
    assert horizon["exclusion_reason_code"] == "MULTIPLE_RULES_FAILED"
    reason = horizon["exclusion_reason"]
    assert "Applicant age" in reason
    assert "monthly income" in reason
    assert "work type" in reason


def test_invalid_stored_policy_json_produces_policy_configuration_invalid(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """19. Invalid stored policy JSON produces POLICY_CONFIGURATION_INVALID."""
    # Add a corrupt policy
    corrupt = LenderPolicy(
        lender_code="CORRUPT_LENDER",
        lender_name="Corrupt Lender",
        policy_version="v1.0",
        is_active=True,
        rules={"min_age": -99, "invalid": True},
    )
    db_session.add(corrupt)
    db_session.commit()

    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    d_map = {d["lender_code"]: d for d in resp.json()["decisions"]}
    assert "CORRUPT_LENDER" in d_map
    assert d_map["CORRUPT_LENDER"]["decision_status"] == "ineligible"
    assert d_map["CORRUPT_LENDER"]["exclusion_reason_code"] == "POLICY_CONFIGURATION_INVALID"


def test_invalid_policy_does_not_crash_other_lenders(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """20. An invalid policy does not crash evaluations for other lenders."""
    corrupt = LenderPolicy(
        lender_code="CORRUPT_LENDER",
        lender_name="Corrupt Lender",
        policy_version="v1.0",
        is_active=True,
        rules={"min_age": 150},  # Fails le=100
    )
    db_session.add(corrupt)
    db_session.commit()

    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id, age=30, monthly_income=Decimal("60000.00"))

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    d_map = {d["lender_code"]: d for d in resp.json()["decisions"]}
    # Corrupt lender evaluated safely as ineligible
    assert d_map["CORRUPT_LENDER"]["decision_status"] == "ineligible"
    # Other lenders evaluated normally
    assert d_map["APEX_FINANCIAL"]["decision_status"] == "eligible"
    assert d_map["HORIZON_CREDIT"]["decision_status"] == "eligible"
    assert d_map["STERLING_LOANS"]["decision_status"] == "eligible"


def test_inactive_policy_is_not_evaluated(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """21. Inactive policy is not evaluated."""
    # Deactivate HORIZON_CREDIT
    stmt = select(LenderPolicy).where(LenderPolicy.lender_code == "HORIZON_CREDIT")
    horizon = db_session.execute(stmt).scalar_one()
    horizon.is_active = False
    db_session.commit()

    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    codes = {d["lender_code"] for d in resp.json()["decisions"]}
    assert "HORIZON_CREDIT" not in codes
    assert codes == {"APEX_FINANCIAL", "STERLING_LOANS"}


def test_multiple_active_versions_cause_configuration_failure(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """22. Multiple active versions for one lender cause safe configuration failure (503)."""
    # Insert another active version for APEX_FINANCIAL
    apex_v2 = LenderPolicy(
        lender_code="APEX_FINANCIAL",
        lender_name="Apex Financial",
        policy_version="v2.0",
        is_active=True,
        rules={
            "min_age": 22,
            "min_monthly_income": "28000.00",
            "allowed_work_types": ["salaried"],
        },
    )
    db_session.add(apex_v2)
    db_session.commit()

    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert "Multiple active policy versions detected" in resp.json()["detail"]


def test_no_active_policies_cause_configuration_failure(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """23. No active policies cause safe configuration failure (503)."""
    # Clear all policies
    db_session.query(LenderPolicy).delete()
    db_session.commit()

    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert "No active lender" in resp.json()["detail"]


def test_policy_version_snapshot_recorded_correctly(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """24. Policy version snapshot is recorded correctly."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    for d in resp.json()["decisions"]:
        assert d["policy_version_snapshot"] == "v1.0"


# ---------------------------------------------------------------------------
# 25–34: Match Run & History Lifecycle Tests
# ---------------------------------------------------------------------------


def test_one_run_created_for_successful_matching_call(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """25. One run is created for a successful matching call."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    run_id = resp.json()["id"]

    runs = db_session.query(MatchRun).filter(MatchRun.application_id == app.id).all()
    assert len(runs) == 1
    assert runs[0].id == run_id


def test_one_decision_per_active_lender_created(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """26. One decision per active lender is created."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    decisions = resp.json()["decisions"]
    assert len(decisions) == 3
    lender_codes = {d["lender_code"] for d in decisions}
    assert lender_codes == {"APEX_FINANCIAL", "HORIZON_CREDIT", "STERLING_LOANS"}


def test_match_run_status_becomes_completed(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """27. Match run status becomes completed."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None


def test_application_status_becomes_matched(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """28. Application status becomes matched."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id, app_status="draft")

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    db_session.refresh(app)
    assert app.status == "matched"


def test_repeated_matching_creates_sequential_run_numbers(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """29. Repeated matching creates run numbers 1 and 2."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    # Run 1
    resp1 = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201
    assert resp1.json()["run_number"] == 1

    # Run 2 (application is now in 'matched' status, which is permitted)
    resp2 = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["run_number"] == 2


def test_previous_runs_and_decisions_remain_unchanged(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """30. Previous runs and decisions remain unchanged."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp1 = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    run1_id = resp1.json()["id"]

    resp2 = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    run2_id = resp2.json()["id"]
    assert run1_id != run2_id

    # Verify run 1 still exists intact in the database
    run1 = db_session.get(MatchRun, run1_id)
    assert run1 is not None
    assert run1.run_number == 1
    assert len(run1.decisions) == 3


def test_run_history_returns_records_in_correct_order(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """31. Run history returns records in chronological run_number order."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = client.get(
        f"/api/v1/applications/{app.id}/matches",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_runs"] == 2
    assert [r["run_number"] for r in data["runs"]] == [1, 2]


def test_empty_history_returns_empty_summary(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
):
    """32. Empty history returns an empty summary."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.get(
        f"/api/v1/applications/{app.id}/matches",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_runs"] == 0
    assert data["runs"] == []


def test_another_customer_matching_history_is_inaccessible(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    matching_customer_b: Tuple[User, str],
    setup_test_policies: None,
):
    """33. Another customer's matching history is inaccessible (404)."""
    user_a, token_a = matching_customer_a
    _, token_b = matching_customer_b
    app_a = _create_app_with_consents(db_session, user_a.id)

    # Customer A performs matching
    client.post(
        f"/api/v1/applications/{app_a.id}/match",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Customer B attempts to view Customer A's match history
    resp = client.get(
        f"/api/v1/applications/{app_a.id}/matches",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Loan application not found."


def test_database_failure_rolls_back_partial_changes(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """34. Database failure rolls back partial matching changes."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id, app_status="draft")

    # Simulate database commit error during matching
    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated database failure")):
        with pytest.raises(RuntimeError):
            client.post(
                f"/api/v1/applications/{app.id}/match",
                headers={"Authorization": f"Bearer {token}"},
            )

    # Verify no partial MatchRun persisted
    runs = db_session.query(MatchRun).filter(MatchRun.application_id == app.id).all()
    assert len(runs) == 0

    # Verify application status remains draft
    db_session.refresh(app)
    assert app.status == "draft"


def test_no_offers_are_created_by_matching_engine(
    client: TestClient,
    db_session: Session,
    matching_customer_a: Tuple[User, str],
    setup_test_policies: None,
):
    """35. Verify that no Offer records are created by Step 8B."""
    user, token = matching_customer_a
    app = _create_app_with_consents(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    # Verify zero records in offers table
    offers_count = db_session.query(Offer).count()
    assert offers_count == 0


def test_unrelated_empty_match_run_is_retained_after_cleanup(db_session: Session):
    """36. Verify that an unrelated empty MatchRun is retained after matching test cleanup."""
    # Create an unrelated user (not matching pytest_matching_ prefix)
    unrelated_user, _ = create_fictional_user(
        db_session,
        email="pytest_unrelated_customer@example.com",
        role="customer",
        full_name="Unrelated Customer",
    )
    unrelated_app = LoanApplication(
        customer_id=unrelated_user.id,
        age=30,
        monthly_income=Decimal("50000.00"),
        work_type="salaried",
        requested_amount=Decimal("100000.00"),
        status="draft",
    )
    db_session.add(unrelated_app)
    db_session.commit()
    db_session.refresh(unrelated_app)

    # Consent for foreign key
    consent = Consent(
        application_id=unrelated_app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add(consent)
    db_session.commit()
    db_session.refresh(consent)

    # Empty match run without decisions
    unrelated_run = MatchRun(
        application_id=unrelated_app.id,
        consent_id=consent.id,
        run_number=1,
        status="started",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(unrelated_run)
    db_session.commit()
    db_session.refresh(unrelated_run)
    run_id = unrelated_run.id

    try:
        # Run matching test policies cleanup
        _clean_test_policies(db_session)

        # Confirm the unrelated empty MatchRun was NOT deleted
        db_run = db_session.get(MatchRun, run_id)
        assert db_run is not None
        assert db_run.id == run_id
    finally:
        # Clean up this unrelated test record safely
        db_session.query(MatchRun).filter(MatchRun.id == run_id).delete(synchronize_session=False)
        db_session.query(Consent).filter(Consent.id == consent.id).delete(synchronize_session=False)
        db_session.query(LoanApplication).filter(LoanApplication.id == unrelated_app.id).delete(
            synchronize_session=False
        )
        db_session.query(User).filter(User.id == unrelated_user.id).delete(synchronize_session=False)
        db_session.commit()
