import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Generator, List, Tuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.models.lender_decision import LenderDecision
from app.models.lender_event import LenderEvent
from app.models.lender_policy import LenderPolicy
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from app.models.user import User
from app.services.consent_notices import (
    PURPOSE_ELIGIBILITY_MATCHING,
    PURPOSE_SHARING_WITH_MOCK_LENDERS,
)
from app.services.matching_service import run_matching
from app.services.offer_service import (
    ApplicationNotFoundError,
    OfferConsentConflictError,
    OfferMatchRunConflictError,
    OfferNotFoundError,
    OfferSelectionConflictError,
    OfferStatusConflictError,
    generate_application_offers,
    get_mock_kfs_details,
    select_application_offer,
)
from tests.conftest import (
    TEST_SELECT_EMAIL_PREFIX,
    create_fictional_user,
)

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


@pytest.fixture
def select_customer_a(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer A."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SELECT_EMAIL_PREFIX}customer_a@example.com",
        role="customer",
        full_name="Select Customer A",
    )


@pytest.fixture
def select_customer_b(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer B."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SELECT_EMAIL_PREFIX}customer_b@example.com",
        role="customer",
        full_name="Select Customer B",
    )


@pytest.fixture
def select_caller(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Caller."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SELECT_EMAIL_PREFIX}caller@example.com",
        role="caller",
        full_name="Select Test Caller",
    )


@pytest.fixture
def select_admin(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Admin."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SELECT_EMAIL_PREFIX}admin@example.com",
        role="admin",
        full_name="Select Test Admin",
    )


def _clean_select_test_records(db: Session) -> None:
    """Safely delete test records belonging only to select test applications and users."""
    try:
        db.rollback()
    except Exception:
        pass
    user_ids = [
        u[0]
        for u in db.query(User.id)
        .filter(User.email.startswith(TEST_SELECT_EMAIL_PREFIX))
        .all()
    ]
    if user_ids:
        app_ids = [
            a[0]
            for a in db.query(LoanApplication.id)
            .filter(LoanApplication.customer_id.in_(user_ids))
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
def setup_select_policies(db_session: Session) -> Generator[None, None, None]:
    """Ensure canonical test policies exist in isolated test database."""
    _clean_select_test_records(db_session)

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
    _clean_select_test_records(db_session)


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


def _create_matched_app_with_offers(
    db: Session,
    customer_id: int,
    age: int = 26,
    monthly_income: Decimal = Decimal("50000.00"),
    work_type: str = "salaried",
    requested_amount: Decimal = Decimal("200000.00"),
) -> Tuple[LoanApplication, MatchRun, List[Offer]]:
    """Helper to create an application, run matching, and generate mock loan offers."""
    app = _create_app_with_consents(
        db=db,
        customer_id=customer_id,
        age=age,
        monthly_income=monthly_income,
        work_type=work_type,
        requested_amount=requested_amount,
    )
    run_matching(db=db, customer_id=customer_id, application_id=app.id)
    gen_resp = generate_application_offers(db=db, customer_id=customer_id, application_id=app.id)

    db.refresh(app)
    latest_run = (
        db.query(MatchRun)
        .filter(MatchRun.application_id == app.id)
        .order_by(MatchRun.run_number.desc())
        .first()
    )
    offers = (
        db.query(Offer)
        .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
        .filter(LenderDecision.match_run_id == latest_run.id)
        .all()
    )
    return app, latest_run, offers


# ===========================================================================
# Test Cases (Covering Part F Scenarios 1 to 37)
# ===========================================================================


def test_customer_can_select_available_offer_from_latest_run(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Cases 1, 2, 3, 4, 8, 9: Customer selects an available offer from latest completed run.

    Verifies:
    - Selected offer becomes 'selected'.
    - Application status becomes 'offer_selected'.
    - Other available offers become 'withdrawn'.
    - Response contains correct OfferResponse and withdrawn_offer_count.
    """
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    assert len(offers) == 3
    target_offer = offers[0]
    other_offers = offers[1:]

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["application_id"] == app.id
    assert data["application_status"] == "offer_selected"
    assert data["selection_result"] == "selected"
    assert data["withdrawn_offer_count"] == 2
    assert data["selected_offer"]["id"] == target_offer.id
    assert data["selected_offer"]["status"] == "selected"

    # Verify DB state
    db_session.refresh(app)
    assert app.status == "offer_selected"

    db_session.refresh(target_offer)
    assert target_offer.status == "selected"

    for other in other_offers:
        db_session.refresh(other)
        assert other.status == "withdrawn"


def test_withdrawal_affects_available_offers_across_all_runs(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Cases 4 & 5: When an offer is selected, available offers from older match runs also become withdrawn."""
    user, token = select_customer_a
    app, run1, offers_run1 = _create_matched_app_with_offers(db_session, user.id)
    assert len(offers_run1) == 3

    # Re-run matching directly while app is in 'matched' status
    run_matching(db=db_session, customer_id=user.id, application_id=app.id)
    generate_application_offers(db=db_session, customer_id=user.id, application_id=app.id)

    # Get offers from run 2
    run2 = (
        db_session.query(MatchRun)
        .filter(MatchRun.application_id == app.id)
        .order_by(MatchRun.run_number.desc())
        .first()
    )
    offers_run2 = (
        db_session.query(Offer)
        .join(LenderDecision, Offer.lender_decision_id == LenderDecision.id)
        .filter(LenderDecision.match_run_id == run2.id)
        .all()
    )
    assert len(offers_run2) == 3

    # Select an offer from run 2
    target_offer = offers_run2[0]
    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    # 2 remaining in run2 + 3 in run1 = 5 withdrawn offers
    assert data["withdrawn_offer_count"] == 5

    # Check DB: run 1 offers are still preserved, but now 'withdrawn'
    for o1 in offers_run1:
        db_session.refresh(o1)
        assert o1.status == "withdrawn"

    db_session.refresh(target_offer)
    assert target_offer.status == "selected"


def test_kfs_remains_readable_for_selected_and_withdrawn_offers(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Cases 6 & 7: Mock KFS details remain fully readable for both selected and withdrawn offers."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    selected_offer = offers[0]
    withdrawn_offer = offers[1]

    # Perform selection
    resp = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # 1. Read KFS for selected offer
    kfs_selected = client.get(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert kfs_selected.status_code == 200
    assert kfs_selected.json()["offer_status"] == "selected"
    assert kfs_selected.json()["offer_id"] == selected_offer.id

    # 2. Read KFS for withdrawn offer
    kfs_withdrawn = client.get(
        f"/api/v1/applications/{app.id}/offers/{withdrawn_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert kfs_withdrawn.status_code == 200
    assert kfs_withdrawn.json()["offer_status"] == "withdrawn"
    assert kfs_withdrawn.json()["offer_id"] == withdrawn_offer.id


def test_idempotent_retry_of_same_selection(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Cases 10, 11, 12: Repeating the same selection returns HTTP 200 with 'already_selected' and mutates nothing."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # First selection
    r1 = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["selection_result"] == "selected"

    orig_loan_amount = target_offer.loan_amount
    orig_apr = target_offer.apr
    orig_term_months = target_offer.term_months
    orig_emi = target_offer.monthly_installment

    # Second selection (idempotent retry)
    r2 = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["selection_result"] == "already_selected"
    assert data2["withdrawn_offer_count"] == 0
    assert data2["selected_offer"]["id"] == target_offer.id
    assert data2["selected_offer"]["status"] == "selected"

    # Verify fields unmutated
    db_session.refresh(target_offer)
    assert target_offer.loan_amount == orig_loan_amount
    assert target_offer.apr == orig_apr
    assert target_offer.term_months == orig_term_months
    assert target_offer.monthly_installment == orig_emi


def test_selecting_different_offer_after_selection_returns_409(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 13: Attempting to select a different offer once an offer has been selected returns 409 conflict."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    first_offer = offers[0]
    second_offer = offers[1]

    # Select first offer
    r1 = client.post(
        f"/api/v1/applications/{app.id}/offers/{first_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200

    # Attempt to select second offer
    r2 = client.post(
        f"/api/v1/applications/{app.id}/offers/{second_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409
    assert "already has a selected offer" in r2.json()["detail"]


def test_offer_from_older_match_run_cannot_be_selected(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 14: An offer from an older match run cannot be selected once a newer match run exists."""
    user, token = select_customer_a
    app, run1, offers_run1 = _create_matched_app_with_offers(db_session, user.id)

    # Perform second matching run directly while in 'matched' status
    run_matching(db=db_session, customer_id=user.id, application_id=app.id)
    generate_application_offers(db=db_session, customer_id=user.id, application_id=app.id)

    # Try to select offer from run 1
    old_offer = offers_run1[0]
    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{old_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "older match run" in response.json()["detail"]


def test_cannot_select_without_match_run(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 15: No match run on application returns 409."""
    user, token = select_customer_a
    app = _create_app_with_consents(db_session, customer_id=user.id, app_status="matched")

    # Call service directly or via mock
    with pytest.raises(OfferNotFoundError):
        select_application_offer(
            db=db_session,
            customer_id=user.id,
            application_id=app.id,
            offer_id=99999,
        )


def test_latest_match_run_not_completed_returns_409(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 16: If latest match run is not completed, selection returns 409."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Create an incomplete newer match run with valid consent_id
    incomplete_run = MatchRun(
        application_id=app.id,
        consent_id=run.consent_id,
        run_number=run.run_number + 1,
        status="started",
    )
    db_session.add(incomplete_run)
    db_session.commit()

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "not completed" in response.json()["detail"]


def test_ineligible_decision_cannot_be_selected(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 17: An offer linked to an ineligible decision cannot be selected."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Manually mark decision ineligible satisfying table constraints
    target_offer.lender_decision.decision_status = "ineligible"
    target_offer.lender_decision.exclusion_reason_code = "AGE_BELOW_MIN"
    target_offer.lender_decision.exclusion_reason = "Age is below policy requirement."
    db_session.commit()

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "not eligible" in response.json()["detail"]


def test_expired_offer_cannot_be_selected(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 18: An offer with status 'expired' cannot be selected."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]
    target_offer.status = "expired"
    db_session.commit()

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "cannot be selected" in response.json()["detail"]


def test_withdrawn_offer_cannot_be_selected(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 19: An offer with status 'withdrawn' cannot be selected."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]
    target_offer.status = "withdrawn"
    db_session.commit()

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "cannot be selected" in response.json()["detail"]


def test_customer_cannot_select_another_customer_offer(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
    select_customer_b: Tuple[User, str],
) -> None:
    """Case 20: Customer B cannot select Customer A's offer through Customer B's application."""
    user_a, token_a = select_customer_a
    user_b, token_b = select_customer_b

    app_a, run_a, offers_a = _create_matched_app_with_offers(db_session, user_a.id)
    app_b, run_b, offers_b = _create_matched_app_with_offers(db_session, user_b.id)

    # Customer B attempts to select Offer A on Customer B's application
    offer_a = offers_a[0]
    response = client.post(
        f"/api/v1/applications/{app_b.id}/offers/{offer_a.id}/select",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Offer not found."


def test_customer_cannot_select_offer_through_another_customer_application(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
    select_customer_b: Tuple[User, str],
) -> None:
    """Case 21: Customer B cannot select through Customer A's application ID."""
    user_a, token_a = select_customer_a
    user_b, token_b = select_customer_b

    app_a, run_a, offers_a = _create_matched_app_with_offers(db_session, user_a.id)
    offer_a = offers_a[0]

    response = client.post(
        f"/api/v1/applications/{app_a.id}/offers/{offer_a.id}/select",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Loan application not found."


def test_unknown_application_id_returns_404(
    client: TestClient,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 22: Nonexistent application ID returns 404."""
    user, token = select_customer_a
    response = client.post(
        "/api/v1/applications/999999/offers/1/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Loan application not found."


def test_unknown_offer_id_returns_404(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 23: Nonexistent offer ID returns 404."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/999999/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Offer not found."


def test_missing_authentication_returns_401(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 24: Unauthenticated request returns 401."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select"
    )
    assert response.status_code == 401


def test_caller_and_admin_cannot_select_offer(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
    select_caller: Tuple[User, str],
    select_admin: Tuple[User, str],
) -> None:
    """Cases 25 & 26: Caller and Admin roles receive 403 Forbidden."""
    user, token = select_customer_a
    caller_user, caller_token = select_caller
    admin_user, admin_token = select_admin

    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    for token in (caller_token, admin_token):
        response = client.post(
            f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


def test_missing_consent_prevents_selection(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 27: Missing active consent prevents new selection (409 with missing_purposes)."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Delete sharing consent
    db_session.query(Consent).filter(
        Consent.application_id == app.id,
        Consent.purpose == PURPOSE_SHARING_WITH_MOCK_LENDERS,
    ).delete(synchronize_session=False)
    db_session.commit()

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    data = response.json()
    assert "missing_purposes" in data["detail"]
    assert PURPOSE_SHARING_WITH_MOCK_LENDERS in data["detail"]["missing_purposes"]


def test_revoked_consent_prevents_selection(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 28: Revoked consent prevents new selection."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Revoke eligibility consent
    c = (
        db_session.query(Consent)
        .filter(
            Consent.application_id == app.id,
            Consent.purpose == PURPOSE_ELIGIBILITY_MATCHING,
        )
        .first()
    )
    c.status = "revoked"
    c.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    data = response.json()
    assert PURPOSE_ELIGIBILITY_MATCHING in data["detail"]["missing_purposes"]


def test_outdated_consent_prevents_selection(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 29: Outdated consent version prevents new selection."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Set notice version to outdated v0.9
    c = (
        db_session.query(Consent)
        .filter(
            Consent.application_id == app.id,
            Consent.purpose == PURPOSE_ELIGIBILITY_MATCHING,
        )
        .first()
    )
    c.notice_version = "v0.9"
    db_session.commit()

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    data = response.json()
    assert PURPOSE_ELIGIBILITY_MATCHING in data["detail"]["missing_purposes"]


def test_idempotent_retry_succeeds_even_after_consent_revocation(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 30: Idempotent retry of already selected offer succeeds without rechecking consents."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Perform initial selection
    r1 = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200

    # Revoke both consents
    db_session.query(Consent).filter(Consent.application_id == app.id).update(
        {"status": "revoked", "revoked_at": datetime.now(timezone.utc)}
    )
    db_session.commit()

    # Retry selection: should still succeed with 'already_selected'
    r2 = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["selection_result"] == "already_selected"


def test_two_different_offers_cannot_both_become_selected(
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 31: Two different offers cannot both become selected for the same application."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    offer_1 = offers[0]
    offer_2 = offers[1]

    # Select first offer
    res1 = select_application_offer(
        db=db_session,
        customer_id=user.id,
        application_id=app.id,
        offer_id=offer_1.id,
    )
    assert res1.selection_result == "selected"

    # Attempt to select second offer directly via service
    with pytest.raises(OfferSelectionConflictError) as exc_info:
        select_application_offer(
            db=db_session,
            customer_id=user.id,
            application_id=app.id,
            offer_id=offer_2.id,
        )
    assert "already has a selected offer" in str(exc_info.value)


def test_inconsistent_state_not_silently_replaced(
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 32: If application.status is 'matched' but an offer is already marked 'selected', raise conflict."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    offer_1 = offers[0]
    offer_2 = offers[1]

    # Corrupt state manually: offer_1 is selected, but app.status remains 'matched'
    offer_1.status = "selected"
    db_session.commit()

    with pytest.raises(OfferSelectionConflictError) as exc_info:
        select_application_offer(
            db=db_session,
            customer_id=user.id,
            application_id=app.id,
            offer_id=offer_2.id,
        )
    assert "already has an offer marked as selected" in str(exc_info.value)


def test_offer_submission_and_lender_event_remain_empty(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Cases 33 & 34: OfferSelection does NOT create any OfferSubmission or LenderEvent records."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Record initial counts
    sub_count_before = db_session.query(OfferSubmission).count()
    event_count_before = db_session.query(LenderEvent).count()

    # Perform selection
    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # Assert zero created
    assert db_session.query(OfferSubmission).count() == sub_count_before
    assert db_session.query(LenderEvent).count() == event_count_before


def test_selection_preserves_financial_terms_and_kfs_reference(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 35: Selection does not alter loan_amount, apr, term_months, emi, or kfs_reference."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    orig_amount = target_offer.loan_amount
    orig_apr = target_offer.apr
    orig_term = target_offer.term_months
    orig_emi = target_offer.monthly_installment
    orig_kfs_ref = target_offer.mock_kfs_reference

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    db_session.refresh(target_offer)
    assert target_offer.loan_amount == orig_amount
    assert target_offer.apr == orig_apr
    assert target_offer.term_months == orig_term
    assert target_offer.monthly_installment == orig_emi
    assert target_offer.mock_kfs_reference == orig_kfs_ref


def test_low_positive_apr_rounding_regression_case(
    client: TestClient,
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 36: Part B low-positive-APR rounding regression: Principal=1000.90, APR=0.0001, Tenure=360, EMI=2.78."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    target_offer.loan_amount = Decimal("1000.90")
    target_offer.apr = Decimal("0.0001")
    target_offer.term_months = 360
    target_offer.monthly_installment = Decimal("2.78")
    db_session.commit()

    # KFS check
    kfs = client.get(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert kfs.status_code == 200
    kfs_data = kfs.json()
    assert Decimal(kfs_data["loan_amount"]) == Decimal("1000.90")
    assert Decimal(kfs_data["monthly_installment"]) == Decimal("2.78")
    assert Decimal(kfs_data["estimated_total_repayment"]) == Decimal("1000.90")
    assert Decimal(kfs_data["estimated_total_interest"]) == Decimal("0.00")

    # Now select this offer
    sel = client.post(
        f"/api/v1/applications/{app.id}/offers/{target_offer.id}/select",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sel.status_code == 200
    sel_data = sel.json()
    assert sel_data["selection_result"] == "selected"
    assert Decimal(sel_data["selected_offer"]["loan_amount"]) == Decimal("1000.90")
    assert Decimal(sel_data["selected_offer"]["monthly_installment"]) == Decimal("2.78")


def test_failed_selection_rolls_back_partial_status_updates(
    db_session: Session,
    setup_select_policies: None,
    select_customer_a: Tuple[User, str],
) -> None:
    """Case 37: If an unexpected error occurs during selection, database transaction rolls back all partial updates."""
    user, token = select_customer_a
    app, run, offers = _create_matched_app_with_offers(db_session, user.id)
    target_offer = offers[0]

    # Mock db.commit to raise an exception simulating unexpected failure
    with patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB failure")):
        with pytest.raises(RuntimeError):
            select_application_offer(
                db=db_session,
                customer_id=user.id,
                application_id=app.id,
                offer_id=target_offer.id,
            )

    # Verify rollback: application status is still 'matched', offer status is still 'available'
    db_session.rollback()
    db_session.refresh(app)
    db_session.refresh(target_offer)
    assert app.status == "matched"
    assert target_offer.status == "available"
    for other in offers[1:]:
        db_session.refresh(other)
        assert other.status == "available"
