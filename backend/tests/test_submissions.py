import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Generator, List, Tuple
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.mock_lenders import (
    MockLenderAdapterError,
    mock_lender_client,
)
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
    generate_application_offers,
    select_application_offer,
)
from app.services.submission_service import (
    SubmissionAdapterError,
    SubmissionApplicationNotFoundError,
    SubmissionConflictError,
    SubmissionConsentConflictError,
    SubmissionOfferNotFoundError,
    submit_selected_offer,
)
from tests.conftest import (
    TEST_SUBMISSION_EMAIL_PREFIX,
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
def sub_customer_a(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer A."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SUBMISSION_EMAIL_PREFIX}customer_a@example.com",
        role="customer",
        full_name="Submission Customer A",
    )


@pytest.fixture
def sub_customer_b(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Customer B."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SUBMISSION_EMAIL_PREFIX}customer_b@example.com",
        role="customer",
        full_name="Submission Customer B",
    )


@pytest.fixture
def sub_caller(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Caller."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SUBMISSION_EMAIL_PREFIX}caller@example.com",
        role="caller",
        full_name="Submission Test Caller",
    )


@pytest.fixture
def sub_admin(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated test Admin."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_SUBMISSION_EMAIL_PREFIX}admin@example.com",
        role="admin",
        full_name="Submission Test Admin",
    )


def _clean_sub_test_records(db: Session) -> None:
    """Safely delete test records belonging only to submission test applications and users."""
    try:
        db.rollback()
    except Exception:
        pass

    user_ids = [
        u[0]
        for u in db.query(User.id)
        .filter(User.email.startswith(TEST_SUBMISSION_EMAIL_PREFIX))
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
            # Delete events
            db.query(LenderEvent).filter(
                LenderEvent.submission_id.in_(
                    db.query(OfferSubmission.id).filter(
                        OfferSubmission.application_id.in_(app_ids)
                    )
                )
            ).delete(synchronize_session=False)

            # Delete submissions
            db.query(OfferSubmission).filter(
                OfferSubmission.application_id.in_(app_ids)
            ).delete(synchronize_session=False)

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
def setup_sub_policies(db_session: Session) -> Generator[None, None, None]:
    """Ensure canonical test policies exist in isolated test database."""
    _clean_sub_test_records(db_session)

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
    _clean_sub_test_records(db_session)


def _create_app_with_selected_offer(
    db: Session,
    customer_id: int,
    age: int = 26,
    monthly_income: Decimal = Decimal("50000.00"),
    work_type: str = "salaried",
    requested_amount: Decimal = Decimal("200000.00"),
) -> Tuple[LoanApplication, Offer, List[Offer]]:
    """Helper to create an application, run matching, generate offers, and select the first offer."""
    app = LoanApplication(
        customer_id=customer_id,
        age=age,
        monthly_income=monthly_income,
        work_type=work_type,
        requested_amount=requested_amount,
        status="draft",
        lead_id=None,
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

    run_matching(db=db, customer_id=customer_id, application_id=app.id)
    generate_application_offers(db=db, customer_id=customer_id, application_id=app.id)

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

    chosen = offers[0]
    select_application_offer(
        db=db,
        customer_id=customer_id,
        application_id=app.id,
        offer_id=chosen.id,
    )
    db.refresh(app)
    db.refresh(chosen)
    return app, chosen, offers[1:]


# ===========================================================================
# Test Cases (Covering Scenarios 1 to 50)
# ===========================================================================


def test_customer_can_submit_selected_offer(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 1, 2, 3, 4, 5, 6, 7, 8, 9, 49, 50: Successful offer submission and state verification."""
    user, token = sub_customer_a
    app, selected_offer, other_offers = _create_app_with_selected_offer(db_session, user.id)

    orig_loan_amount = selected_offer.loan_amount
    orig_apr = selected_offer.apr
    orig_term = selected_offer.term_months
    orig_emi = selected_offer.monthly_installment
    key = str(uuid.uuid4())

    response = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    assert response.status_code == 200
    data = response.json()

    # 1-4. Response verification
    assert data["application_id"] == app.id
    assert data["offer_id"] == selected_offer.id
    assert data["status"] == "submitted"
    assert data["submission_result"] == "created"
    assert data["mock_reference"].startswith("MOCK-SUB-")
    assert "key" not in data  # Never exposes idempotency key (Case 50)
    assert "idempotency_key" not in data

    # 49. Lender metadata
    assert data["lender_code"] == selected_offer.lender_decision.lender_policy.lender_code
    assert data["lender_name"] == selected_offer.lender_decision.lender_policy.lender_name
    assert data["policy_version"] == selected_offer.lender_decision.policy_version_snapshot

    # 5. Application status becomes submitted
    db_session.refresh(app)
    assert app.status == "submitted"

    # 6-7. Selected offer remains selected with unchanged financial terms
    db_session.refresh(selected_offer)
    assert selected_offer.status == "selected"
    assert selected_offer.loan_amount == orig_loan_amount
    assert selected_offer.apr == orig_apr
    assert selected_offer.term_months == orig_term
    assert selected_offer.monthly_installment == orig_emi

    # 8. Other offers remain withdrawn
    for other in other_offers:
        db_session.refresh(other)
        assert other.status == "withdrawn"

    # 9. No LenderEvent is created
    assert db_session.query(LenderEvent).count() == 0


def test_adapter_called_with_correct_parameters_and_no_pii(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 10, 11, 12: Verify mock lender adapter receives only lender_code and submission_id (no PII)."""
    user, token = sub_customer_a
    app, selected_offer, other_offers = _create_app_with_selected_offer(db_session, user.id)
    key = str(uuid.uuid4())

    with patch.object(
        mock_lender_client, "submit_offer", wraps=mock_lender_client.submit_offer
    ) as spy_submit:
        resp = client.post(
            f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        )
        assert resp.status_code == 200

        spy_submit.assert_called_once()
        call_kwargs = spy_submit.call_args.kwargs
        call_args = spy_submit.call_args.args

        # Case 10: correct lender code
        expected_code = selected_offer.lender_decision.lender_policy.lender_code
        if "lender_code" in call_kwargs:
            assert call_kwargs["lender_code"] == expected_code
        else:
            assert call_args[0] == expected_code

        # Case 11: correct submission ID
        submission = db_session.query(OfferSubmission).filter(OfferSubmission.application_id == app.id).first()
        if "submission_id" in call_kwargs:
            assert call_kwargs["submission_id"] == submission.id
        else:
            assert call_args[1] == submission.id

        # Case 12: no PII in call args or kwargs
        all_passed_values = list(call_args) + list(call_kwargs.values())
        for val in all_passed_values:
            assert user.full_name not in str(val)
            assert user.email not in str(val)


def test_idempotency_key_header_validations(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 13, 14, 15, 16, 17: Header validation tests for Idempotency-Key."""
    user, token = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)

    # 13. Missing Idempotency-Key returns 422
    r_missing = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_missing.status_code == 422
    assert "Missing required header" in r_missing.json()["detail"]

    # 14. Blank key returns 422
    r_blank = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": ""},
    )
    assert r_blank.status_code == 422

    # 15. Whitespace-only key returns 422
    r_ws = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "    "},
    )
    assert r_ws.status_code == 422

    # 16. Key too long (>128 chars) returns 422
    too_long = "a" * 129
    r_long = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": too_long},
    )
    assert r_long.status_code == 422

    # Key too short (<8 chars) returns 422
    r_short = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "short"},
    )
    assert r_short.status_code == 422

    # 17. Valid UUID-style key returns 200
    valid_uuid_key = str(uuid.uuid4())
    r_valid = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": valid_uuid_key},
    )
    assert r_valid.status_code == 200
    assert r_valid.json()["submission_result"] == "created"


def test_idempotent_replay_of_exact_request(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 18, 19, 20, 47: Repeating same submission request with same key replays without calling adapter."""
    user, token = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)
    key = str(uuid.uuid4())

    # First call
    r1 = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["submission_result"] == "created"

    submission_count = db_session.query(OfferSubmission).filter(OfferSubmission.application_id == app.id).count()
    assert submission_count == 1

    # Second call (replay) with mock spy
    with patch.object(mock_lender_client, "submit_offer") as mock_spy:
        r2 = client.post(
            f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["submission_result"] == "replayed"
        assert d2["id"] == d1["id"]
        assert d2["mock_reference"] == d1["mock_reference"]

        # Case 19: adapter not called again
        mock_spy.assert_not_called()

        # Case 20 & 47: zero duplicate submissions created
        assert db_session.query(OfferSubmission).filter(OfferSubmission.application_id == app.id).count() == 1


def test_idempotency_conflicts(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
    sub_customer_b: Tuple[User, str],
) -> None:
    """Cases 21, 22, 23, 24: Reusing key across different offers/applications or different key for same app."""
    user_a, token_a = sub_customer_a
    user_b, token_b = sub_customer_b

    app_a, offer_a, other_a = _create_app_with_selected_offer(db_session, user_a.id)
    app_b, offer_b, other_b = _create_app_with_selected_offer(db_session, user_b.id)

    key_shared = str(uuid.uuid4())

    # Submit app A with key_shared
    r1 = client.post(
        f"/api/v1/applications/{app_a.id}/offers/{offer_a.id}/submit",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": key_shared},
    )
    assert r1.status_code == 200

    # Case 22: Same key used with a different application returns 409
    r_diff_app = client.post(
        f"/api/v1/applications/{app_b.id}/offers/{offer_b.id}/submit",
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": key_shared},
    )
    assert r_diff_app.status_code == 409
    assert "already been used" in r_diff_app.json()["detail"]

    # Case 23: Different key used for same application returns 409
    different_key = str(uuid.uuid4())
    r_diff_key = client.post(
        f"/api/v1/applications/{app_a.id}/offers/{offer_a.id}/submit",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": different_key},
    )
    assert r_diff_key.status_code == 409
    assert "different Idempotency-Key" in r_diff_key.json()["detail"]

    # Case 21 & 24: Same key used with different offer on app A returns 409
    r_diff_offer = client.post(
        f"/api/v1/applications/{app_a.id}/offers/{other_a[0].id}/submit",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": key_shared},
    )
    assert r_diff_offer.status_code == 409


def test_cannot_submit_available_withdrawn_or_expired_offers(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 25, 26, 27, 28: Offers not in 'selected' status or ineligible decisions cannot be submitted."""
    user, token = sub_customer_a
    app, selected_offer, other_offers = _create_app_with_selected_offer(db_session, user.id)
    withdrawn_offer = other_offers[0]

    # Case 26: Withdrawn offer cannot be submitted
    r_withdrawn = client.post(
        f"/api/v1/applications/{app.id}/offers/{withdrawn_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_withdrawn.status_code == 409
    assert "expected 'selected'" in r_withdrawn.json()["detail"]

    # Case 25: Available offer cannot be submitted
    withdrawn_offer.status = "available"
    db_session.commit()
    r_avail = client.post(
        f"/api/v1/applications/{app.id}/offers/{withdrawn_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_avail.status_code == 409
    assert "expected 'selected'" in r_avail.json()["detail"]

    # Case 27: Expired offer cannot be submitted
    withdrawn_offer.status = "expired"
    db_session.commit()
    r_exp = client.post(
        f"/api/v1/applications/{app.id}/offers/{withdrawn_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_exp.status_code == 409

    # Case 28: Ineligible decision cannot be submitted
    selected_offer.lender_decision.decision_status = "ineligible"
    selected_offer.lender_decision.exclusion_reason_code = "AGE_BELOW_MIN"
    selected_offer.lender_decision.exclusion_reason = "Age policy violated"
    db_session.commit()
    r_inelig = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_inelig.status_code == 409
    assert "not 'eligible'" in r_inelig.json()["detail"]


def test_customer_ownership_and_scoping(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
    sub_customer_b: Tuple[User, str],
) -> None:
    """Cases 29, 30, 31, 32: Scoping and ownership restrictions (404)."""
    user_a, token_a = sub_customer_a
    user_b, token_b = sub_customer_b

    app_a, offer_a, _ = _create_app_with_selected_offer(db_session, user_a.id)
    app_b, offer_b, _ = _create_app_with_selected_offer(db_session, user_b.id)

    # Case 29: Customer B attempts to submit Customer A's application -> 404
    r1 = client.post(
        f"/api/v1/applications/{app_a.id}/offers/{offer_a.id}/submit",
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r1.status_code == 404
    assert r1.json()["detail"] == "Loan application not found."

    # Case 30: Offer A under Application B -> 404
    r2 = client.post(
        f"/api/v1/applications/{app_b.id}/offers/{offer_a.id}/submit",
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r2.status_code == 404
    assert r2.json()["detail"] == "Offer not found."

    # Case 31: Unknown application ID -> 404
    r3 = client.post(
        f"/api/v1/applications/999999/offers/{offer_a.id}/submit",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r3.status_code == 404

    # Case 32: Unknown offer ID -> 404
    r4 = client.post(
        f"/api/v1/applications/{app_a.id}/offers/999999/submit",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r4.status_code == 404


def test_application_lifecycle_and_inconsistent_selection_state(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 33 & 34: Non-offer_selected application or inconsistent selection state returns 409."""
    user, token = sub_customer_a
    app, selected_offer, other_offers = _create_app_with_selected_offer(db_session, user.id)

    # Case 33: Application status is 'matched', not 'offer_selected'
    app.status = "matched"
    db_session.commit()
    r_matched = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_matched.status_code == 409
    assert "expected 'offer_selected'" in r_matched.json()["detail"]

    # Case 34: Inconsistent state (app is offer_selected, but 2 offers are marked 'selected')
    app.status = "offer_selected"
    other_offers[0].status = "selected"
    db_session.commit()
    r_inconsistent = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_inconsistent.status_code == 409
    assert "inconsistent selection state" in r_inconsistent.json()["detail"]


def test_consent_verifications_for_new_submission_and_replay(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 35, 36, 37, 38: Missing, revoked, and outdated consents prevent new submission; replay succeeds."""
    user, token = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)

    # Case 35: Missing consent prevents new submission
    db_session.query(Consent).filter(
        Consent.application_id == app.id,
        Consent.purpose == PURPOSE_SHARING_WITH_MOCK_LENDERS,
    ).delete(synchronize_session=False)
    db_session.commit()

    r_missing = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_missing.status_code == 409
    assert PURPOSE_SHARING_WITH_MOCK_LENDERS in r_missing.json()["detail"]["missing_purposes"]

    # Restore consent
    c_new = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add(c_new)
    db_session.commit()

    # Case 36: Revoked consent prevents new submission
    c_new.status = "revoked"
    c_new.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    r_revoked = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_revoked.status_code == 409

    # Case 37: Outdated consent version prevents new submission
    c_new.status = "granted"
    c_new.notice_version = "v0.9"
    db_session.commit()

    r_outdated = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_outdated.status_code == 409

    # Restore correct consent and submit successfully
    c_new.notice_version = "v1.0"
    db_session.commit()
    replay_key = str(uuid.uuid4())

    r_success = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": replay_key},
    )
    assert r_success.status_code == 200

    # Case 38: Revoke consents now; replay still succeeds!
    db_session.query(Consent).filter(Consent.application_id == app.id).update(
        {"status": "revoked", "revoked_at": datetime.now(timezone.utc)}
    )
    db_session.commit()

    r_replay = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": replay_key},
    )
    assert r_replay.status_code == 200
    assert r_replay.json()["submission_result"] == "replayed"


def test_auth_and_rbac_restrictions(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
    sub_caller: Tuple[User, str],
    sub_admin: Tuple[User, str],
) -> None:
    """Cases 39, 40, 41: Caller and Admin return 403; unauthenticated returns 401."""
    user, token = sub_customer_a
    caller_user, caller_token = sub_caller
    admin_user, admin_token = sub_admin

    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)

    # 41. Missing auth -> 401
    r_unauth = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_unauth.status_code == 401

    # 39. Caller -> 403
    r_caller = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {caller_token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_caller.status_code == 403

    # 40. Admin -> 403
    r_admin = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_admin.status_code == 403


def test_adapter_failure_rolls_back_transaction(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Cases 42, 43, 44: When mock adapter raises an error, rollback ensures no partial submission is saved and retry works."""
    user, token = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)
    key = str(uuid.uuid4())

    with patch.object(
        mock_lender_client, "submit_offer", side_effect=MockLenderAdapterError("Simulated mock timeout")
    ):
        response = client.post(
            f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
        )
        assert response.status_code == 503
        assert "Simulated mock timeout" in response.json()["detail"]

    # Case 43: Application remains offer_selected
    db_session.refresh(app)
    assert app.status == "offer_selected"

    # Case 44: No OfferSubmission persisted
    assert db_session.query(OfferSubmission).filter(OfferSubmission.application_id == app.id).count() == 0

    # Subsequent retry with same key now succeeds after adapter recovers
    r_retry = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    assert r_retry.status_code == 200
    assert r_retry.json()["submission_result"] == "created"


def test_replay_preserves_current_stored_submission_status(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Case 45: If submission status later moves to 'accepted' (e.g. via future webhook), replay preserves 'accepted'."""
    user, token = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)
    key = str(uuid.uuid4())

    # Submit
    r1 = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    assert r1.status_code == 200

    # Simulate future status advancement to 'accepted'
    sub = db_session.query(OfferSubmission).filter(OfferSubmission.application_id == app.id).first()
    sub.status = "accepted"
    db_session.commit()

    # Replay
    r2 = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    assert r2.status_code == 200
    assert r2.json()["submission_result"] == "replayed"
    assert r2.json()["status"] == "accepted"


def test_database_unique_constraints_enforced(
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Case 46: Database unique constraints prevent duplicate submissions on application_id, offer_id, and key."""
    user, token = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)

    key1 = str(uuid.uuid4())
    sub1 = OfferSubmission(
        application_id=app.id,
        offer_id=selected_offer.id,
        idempotency_key=key1,
        status="submitted",
        mock_reference="MOCK-1",
    )
    db_session.add(sub1)
    db_session.commit()

    # 1. Duplicate application_id violates unique constraint
    sub_dup_app = OfferSubmission(
        application_id=app.id,
        offer_id=selected_offer.id + 1,
        idempotency_key=str(uuid.uuid4()),
        status="submitted",
        mock_reference="MOCK-2",
    )
    db_session.add(sub_dup_app)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 2. Duplicate offer_id violates unique constraint
    sub_dup_offer = OfferSubmission(
        application_id=app.id + 1,
        offer_id=selected_offer.id,
        idempotency_key=str(uuid.uuid4()),
        status="submitted",
        mock_reference="MOCK-3",
    )
    db_session.add(sub_dup_offer)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 3. Duplicate idempotency_key violates unique constraint
    sub_dup_key = OfferSubmission(
        application_id=app.id + 1,
        offer_id=selected_offer.id + 1,
        idempotency_key=key1,
        status="submitted",
        mock_reference="MOCK-4",
    )
    db_session.add(sub_dup_key)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_kfs_remains_readable_after_submission(
    client: TestClient,
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Case 48: KFS disclosure details remain accessible and accurate after submission."""
    user, token = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)
    key = str(uuid.uuid4())

    sub_resp = client.post(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    assert sub_resp.status_code == 200

    kfs_resp = client.get(
        f"/api/v1/applications/{app.id}/offers/{selected_offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert kfs_resp.status_code == 200
    kfs_data = kfs_resp.json()
    assert kfs_data["offer_id"] == selected_offer.id
    assert kfs_data["offer_status"] == "selected"
    assert Decimal(kfs_data["loan_amount"]) == selected_offer.loan_amount


def test_mock_lender_adapter_unsupported_lender_code() -> None:
    """Verify that MockLenderClient rejects unsupported lender codes with controlled exception."""
    from app.integrations.mock_lenders import UnsupportedLenderCodeError

    client = mock_lender_client
    with pytest.raises(UnsupportedLenderCodeError) as exc_info:
        client.submit_offer(lender_code="UNKNOWN_BANK_XYZ", submission_id=999)
    assert "Unsupported mock lender code" in str(exc_info.value)


def test_service_level_idempotency_key_validations(
    db_session: Session,
    setup_sub_policies: None,
    sub_customer_a: Tuple[User, str],
) -> None:
    """Direct service call testing invalid key types, whitespace, and length boundaries."""
    user, _ = sub_customer_a
    app, selected_offer, _ = _create_app_with_selected_offer(db_session, user.id)

    # 1. Non-string key
    with pytest.raises(SubmissionConflictError) as exc_info:
        submit_selected_offer(
            db=db_session,
            customer_id=user.id,
            application_id=app.id,
            offer_id=selected_offer.id,
            idempotency_key=12345,  # type: ignore
        )
    assert "valid string" in str(exc_info.value)

    # 2. Blank key
    with pytest.raises(SubmissionConflictError) as exc_info:
        submit_selected_offer(
            db=db_session,
            customer_id=user.id,
            application_id=app.id,
            offer_id=selected_offer.id,
            idempotency_key="   ",
        )
    assert "cannot be empty" in str(exc_info.value)

    # 3. Too short (<8 chars)
    with pytest.raises(SubmissionConflictError) as exc_info:
        submit_selected_offer(
            db=db_session,
            customer_id=user.id,
            application_id=app.id,
            offer_id=selected_offer.id,
            idempotency_key="1234567",
        )
    assert "between 8 and 128 characters" in str(exc_info.value)

