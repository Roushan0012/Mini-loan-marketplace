import json
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Generator, List, Tuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, settings
from app.core.webhook_security import (
    create_mock_webhook_signature,
    verify_mock_webhook_signature,
)
from app.db.session import SessionLocal
from app.models.consent import Consent
from app.models.lender_decision import LenderDecision
from app.models.lender_event import LenderEvent
from app.models.lender_policy import LenderPolicy
from app.models.loan_application import LoanApplication
from app.models.match_run import MatchRun
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from app.models.user import User
from app.schemas.lender_event import MockLenderWebhookEvent
from app.services.consent_notices import (
    PURPOSE_ELIGIBILITY_MATCHING,
    PURPOSE_SHARING_WITH_MOCK_LENDERS,
)
from app.services.lender_event_service import (
    LenderEventConflictError,
    SubmissionNotFoundError,
    process_mock_lender_event,
)
from app.services.matching_service import run_matching
from app.services.offer_service import (
    generate_application_offers,
    select_application_offer,
)
from app.services.submission_service import submit_selected_offer
from tests.conftest import (
    TEST_EVENT_EMAIL_PREFIX,
    create_fictional_user,
)

TEST_WEBHOOK_SECRET = "test-webhook-secret-strictly-32-chars-long-mock-lender-12345"

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


@pytest.fixture(autouse=True)
def configure_test_webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a valid test webhook signing secret for test runs."""
    monkeypatch.setattr(settings, "MOCK_LENDER_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)


@pytest.fixture
def event_customer_a(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated Customer A for event tests."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_EVENT_EMAIL_PREFIX}customer_a@example.com",
        role="customer",
        full_name="Event Customer A",
    )


@pytest.fixture
def event_customer_b(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated Customer B for event tests."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_EVENT_EMAIL_PREFIX}customer_b@example.com",
        role="customer",
        full_name="Event Customer B",
    )


@pytest.fixture
def event_caller(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated Caller."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_EVENT_EMAIL_PREFIX}caller@example.com",
        role="caller",
        full_name="Event Test Caller",
    )


@pytest.fixture
def event_admin(db_session: Session) -> Tuple[User, str]:
    """Provide authenticated Admin."""
    return create_fictional_user(
        db_session,
        email=f"{TEST_EVENT_EMAIL_PREFIX}admin@example.com",
        role="admin",
        full_name="Event Test Admin",
    )


def _clean_event_test_records(db: Session) -> None:
    """Safely delete test records belonging only to event test applications and users."""
    try:
        db.rollback()
    except Exception:
        pass

    user_ids = [
        u[0]
        for u in db.query(User.id)
        .filter(User.email.startswith(TEST_EVENT_EMAIL_PREFIX))
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
            # 1. Events linked to test submissions
            db.query(LenderEvent).filter(
                LenderEvent.submission_id.in_(
                    db.query(OfferSubmission.id).filter(
                        OfferSubmission.application_id.in_(app_ids)
                    )
                )
            ).delete(synchronize_session=False)

            # 2. Submissions
            db.query(OfferSubmission).filter(
                OfferSubmission.application_id.in_(app_ids)
            ).delete(synchronize_session=False)

            # 3. Runs and decisions
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
def setup_event_policies(db_session: Session) -> Generator[None, None, None]:
    """Ensure canonical test policies exist in isolated test database."""
    _clean_event_test_records(db_session)

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
    _clean_event_test_records(db_session)


def _create_submitted_application(
    db: Session,
    customer_id: int,
    age: int = 26,
    monthly_income: Decimal = Decimal("50000.00"),
    work_type: str = "salaried",
    requested_amount: Decimal = Decimal("200000.00"),
) -> Tuple[LoanApplication, Offer, OfferSubmission]:
    """Helper to create an application through to 'submitted' status with an OfferSubmission."""
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
    chosen_offer = offers[0]

    select_application_offer(
        db=db,
        customer_id=customer_id,
        application_id=app.id,
        offer_id=chosen_offer.id,
    )
    db.refresh(app)
    db.refresh(chosen_offer)

    sub_resp = submit_selected_offer(
        db=db,
        customer_id=customer_id,
        application_id=app.id,
        offer_id=chosen_offer.id,
        idempotency_key=str(uuid.uuid4()),
    )
    submission = db.query(OfferSubmission).filter(OfferSubmission.id == sub_resp.id).first()
    db.refresh(app)
    db.refresh(chosen_offer)
    return app, chosen_offer, submission


def _build_signed_payload(
    submission: OfferSubmission,
    event_type: str = "lender.accepted",
    sequence_number: int = 1,
    event_id: str = None,
    reason_code: str = None,
    occurred_at: str = None,
    secret: str = TEST_WEBHOOK_SECRET,
) -> Tuple[bytes, Dict[str, str]]:
    """Build raw JSON payload bytes and the matching X-Mock-Lender-Signature header."""
    if event_id is None:
        event_id = f"evt_{uuid.uuid4()}"
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc).isoformat()

    decision = submission.offer.lender_decision if submission.offer else None
    policy = decision.lender_policy if decision else None
    lender_code = policy.lender_code if policy else "APEX_FINANCIAL"

    payload_dict = {
        "event_id": event_id,
        "submission_id": submission.id,
        "mock_reference": submission.mock_reference,
        "lender_code": lender_code,
        "event_type": event_type,
        "sequence_number": sequence_number,
        "occurred_at": occurred_at,
    }
    if reason_code:
        payload_dict["reason_code"] = reason_code

    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = create_mock_webhook_signature(payload_bytes, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Mock-Lender-Signature": sig,
    }
    return payload_bytes, headers


# ===========================================================================
# Test Cases (Covering Part L Scenarios 1 to 57)
# ===========================================================================


# --- 1. HMAC and Security Tests (Cases 1-9) ---


def test_valid_hmac_signature_accepted(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Case 1 & 9: Valid HMAC signature is accepted with 200 OK without requiring Customer JWT."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)

    raw_body, headers = _build_signed_payload(sub, event_type="lender.accepted", sequence_number=1)
    response = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_body, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "lender.accepted"
    assert data["processing_status"] == "processed"
    assert data["submission_status"] == "accepted"
    assert data["application_status"] == "accepted"
    assert data["duplicate"] is False


def test_missing_or_invalid_signature_returns_401(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Cases 2, 3, 4: Missing, invalid, or malformed signature returns 401."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)
    raw_body, headers = _build_signed_payload(sub)

    # 2. Missing signature
    resp_missing = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )
    assert resp_missing.status_code == 401

    # 3. Invalid signature (signed with wrong secret)
    wrong_sig = create_mock_webhook_signature(raw_body, "wrong-test-secret-that-does-not-match-at-all-123")
    resp_invalid = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": wrong_sig},
    )
    assert resp_invalid.status_code == 401

    # 4. Malformed signature
    for malformed in ["sha256=", "invalid-prefix-1234", ""]:
        resp_malformed = client.post(
            "/api/v1/webhooks/mock-lenders/events",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": malformed},
        )
        assert resp_malformed.status_code == 401


def test_missing_webhook_secret_returns_503(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case 5 & 6: Missing secret returns 503 and JWT_SECRET_KEY is NOT used as fallback."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)
    raw_body, headers = _build_signed_payload(sub)

    # Clear webhook secret
    monkeypatch.setattr(settings, "MOCK_LENDER_WEBHOOK_SECRET", None)

    response = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_body, headers=headers)
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_altered_raw_body_fails_signature_verification(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Case 7: Altering even one byte of the request body causes signature verification to fail."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)
    raw_body, headers = _build_signed_payload(sub)

    # Tamper with the raw body bytes
    tampered_body = raw_body.replace(b"APEX_FINANCIAL", b"HORIZON_CREDIT")

    response = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=tampered_body,
        headers=headers,
    )
    assert response.status_code == 401


def test_payload_rejects_pii_and_unexpected_fields(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Case 8: Webhook payload strictly forbids unexpected fields and customer PII."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)

    payload_dict = {
        "event_id": f"evt_{uuid.uuid4()}",
        "submission_id": sub.id,
        "mock_reference": sub.mock_reference,
        "lender_code": "APEX_FINANCIAL",
        "event_type": "lender.accepted",
        "sequence_number": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "customer_email": "leaked_pii@example.com",  # Forbidden extra field!
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = create_mock_webhook_signature(raw_body, TEST_WEBHOOK_SECRET)

    response = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": sig},
    )
    assert response.status_code == 422
    assert "extra_forbidden" in str(response.json()) or "Extra inputs are not permitted" in str(response.json())


# --- 2. Event Outcome Processing and State Transitions (Cases 10-20) ---


@pytest.mark.parametrize(
    "event_type, expected_status",
    [
        ("lender.accepted", "accepted"),
        ("lender.declined", "declined"),
        ("lender.timed_out", "timed_out"),
        ("lender.failed", "failed"),
    ],
)
def test_event_outcome_state_transitions(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
    event_type: str,
    expected_status: str,
) -> None:
    """Cases 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20: Event types transition both submission and app correctly."""
    user, token = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)

    orig_amount = offer.loan_amount
    orig_apr = offer.apr
    orig_idemp_key = sub.idempotency_key
    orig_mock_ref = sub.mock_reference

    raw_body, headers = _build_signed_payload(sub, event_type=event_type, sequence_number=1)
    response = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_body, headers=headers)
    assert response.status_code == 200

    # Refresh records from database
    db_session.refresh(sub)
    db_session.refresh(app)
    db_session.refresh(offer)

    # 10-13. Check status transitions
    assert sub.status == expected_status
    assert app.status == expected_status

    # 14-16. Offer remains selected and financial terms unchanged
    assert offer.status == "selected"
    assert offer.loan_amount == orig_amount
    assert offer.apr == orig_apr

    # 17-18. Submission fields unchanged
    assert sub.idempotency_key == orig_idemp_key
    assert sub.mock_reference == orig_mock_ref

    # 19-20. Event row persisted as 'processed'
    event_row = db_session.query(LenderEvent).filter(LenderEvent.submission_id == sub.id).first()
    assert event_row is not None
    assert event_row.processing_status == "processed"
    assert event_row.event_type == event_type

    # 15. KFS remains readable after terminal outcome
    kfs_resp = client.get(
        f"/api/v1/applications/{app.id}/offers/{offer.id}/kfs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert kfs_resp.status_code == 200
    assert kfs_resp.json()["offer_status"] == "selected"


# --- 3. Reference and Schema Validations (Cases 21-25) ---


def test_reference_validations_and_mismatches(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
    event_customer_b: Tuple[User, str],
) -> None:
    """Cases 21, 22, 23, 24, 25: Unknown IDs, mock_reference mismatch, lender mismatch, and unknown event types."""
    user_a, _ = event_customer_a
    user_b, _ = event_customer_b

    app_a, offer_a, sub_a = _create_submitted_application(db_session, user_a.id)
    app_b, offer_b, sub_b = _create_submitted_application(db_session, user_b.id)

    # 21. Unknown submission ID -> 404
    p1 = {
        "event_id": f"evt_{uuid.uuid4()}",
        "submission_id": 999999,
        "mock_reference": sub_a.mock_reference,
        "lender_code": "APEX_FINANCIAL",
        "event_type": "lender.accepted",
        "sequence_number": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    b1 = json.dumps(p1).encode("utf-8")
    r1 = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=b1,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": create_mock_webhook_signature(b1, TEST_WEBHOOK_SECRET)},
    )
    assert r1.status_code == 404
    assert "not found" in r1.json()["detail"]

    # 22. Mismatched mock_reference -> 404
    p2 = {
        "event_id": f"evt_{uuid.uuid4()}",
        "submission_id": sub_a.id,
        "mock_reference": "MOCK-SUB-WRONG-REF-999",
        "lender_code": "APEX_FINANCIAL",
        "event_type": "lender.accepted",
        "sequence_number": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    b2 = json.dumps(p2).encode("utf-8")
    r2 = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=b2,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": create_mock_webhook_signature(b2, TEST_WEBHOOK_SECRET)},
    )
    assert r2.status_code == 404
    assert "does not match" in r2.json()["detail"]

    # 23 & 24. Mismatched lender_code -> 404
    p3 = {
        "event_id": f"evt_{uuid.uuid4()}",
        "submission_id": sub_a.id,
        "mock_reference": sub_a.mock_reference,
        "lender_code": "HORIZON_CREDIT",  # Wrong lender code
        "event_type": "lender.accepted",
        "sequence_number": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    b3 = json.dumps(p3).encode("utf-8")
    r3 = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=b3,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": create_mock_webhook_signature(b3, TEST_WEBHOOK_SECRET)},
    )
    assert r3.status_code == 404

    # 25. Unknown event_type -> 422
    p4 = {
        "event_id": f"evt_{uuid.uuid4()}",
        "submission_id": sub_a.id,
        "mock_reference": sub_a.mock_reference,
        "lender_code": "APEX_FINANCIAL",
        "event_type": "lender.unknown_action",
        "sequence_number": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    b4 = json.dumps(p4).encode("utf-8")
    r4 = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=b4,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": create_mock_webhook_signature(b4, TEST_WEBHOOK_SECRET)},
    )
    assert r4.status_code == 422


# --- 4. Duplicate Event ID Handling (Cases 26-31) ---


def test_duplicate_event_handling_and_conflicts(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
    event_customer_b: Tuple[User, str],
) -> None:
    """Cases 26, 27, 28, 29, 30, 31: Duplicate event_id replays safely; conflicting content returns 409."""
    user_a, _ = event_customer_a
    user_b, _ = event_customer_b
    app_a, _, sub_a = _create_submitted_application(db_session, user_a.id)
    app_b, _, sub_b = _create_submitted_application(db_session, user_b.id)

    fixed_event_id = f"evt_{uuid.uuid4()}"
    fixed_time = datetime.now(timezone.utc).isoformat()

    raw_body, headers = _build_signed_payload(
        sub_a,
        event_type="lender.accepted",
        sequence_number=1,
        event_id=fixed_event_id,
        occurred_at=fixed_time,
    )

    # 1. First delivery
    r1 = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_body, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["duplicate"] is False
    assert db_session.query(LenderEvent).filter(LenderEvent.event_id == fixed_event_id).count() == 1

    # 26, 27, 28. Exact duplicate replay
    r2 = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True
    # Still exactly 1 row
    assert db_session.query(LenderEvent).filter(LenderEvent.event_id == fixed_event_id).count() == 1

    # 29. Reusing event_id with different event_type -> 409
    p_diff_type = {
        "event_id": fixed_event_id,
        "submission_id": sub_a.id,
        "mock_reference": sub_a.mock_reference,
        "lender_code": "APEX_FINANCIAL",
        "event_type": "lender.declined",  # Different!
        "sequence_number": 1,
        "occurred_at": fixed_time,
    }
    b_diff_type = json.dumps(p_diff_type).encode("utf-8")
    r_diff_type = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=b_diff_type,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": create_mock_webhook_signature(b_diff_type, TEST_WEBHOOK_SECRET)},
    )
    assert r_diff_type.status_code == 409
    assert "different content" in r_diff_type.json()["detail"]

    # 30. Reusing event_id with different sequence_number -> 409
    p_diff_seq = {
        "event_id": fixed_event_id,
        "submission_id": sub_a.id,
        "mock_reference": sub_a.mock_reference,
        "lender_code": "APEX_FINANCIAL",
        "event_type": "lender.accepted",
        "sequence_number": 2,  # Different!
        "occurred_at": fixed_time,
    }
    b_diff_seq = json.dumps(p_diff_seq).encode("utf-8")
    r_diff_seq = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=b_diff_seq,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": create_mock_webhook_signature(b_diff_seq, TEST_WEBHOOK_SECRET)},
    )
    assert r_diff_seq.status_code == 409

    # 31. Reusing event_id with another submission -> 409
    p_diff_sub = {
        "event_id": fixed_event_id,
        "submission_id": sub_b.id,  # Different!
        "mock_reference": sub_b.mock_reference,
        "lender_code": "APEX_FINANCIAL",
        "event_type": "lender.accepted",
        "sequence_number": 1,
        "occurred_at": fixed_time,
    }
    b_diff_sub = json.dumps(p_diff_sub).encode("utf-8")
    r_diff_sub = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=b_diff_sub,
        headers={"Content-Type": "application/json", "X-Mock-Lender-Signature": create_mock_webhook_signature(b_diff_sub, TEST_WEBHOOK_SECRET)},
    )
    assert r_diff_sub.status_code == 409


# --- 5. Event Sequencing and Out-of-Order Processing (Cases 32-38) ---


def test_event_sequencing_and_out_of_order_handling(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Cases 32, 33, 34, 35, 36, 37, 38: Stale events ignored; higher sequence numbers authoritative."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)

    # 33. Sequence 3 received first: it is processed as accepted
    b3, h3 = _build_signed_payload(sub, event_type="lender.accepted", sequence_number=3)
    r3 = client.post("/api/v1/webhooks/mock-lenders/events", content=b3, headers=h3)
    assert r3.status_code == 200
    assert r3.json()["processing_status"] == "processed"
    assert r3.json()["submission_status"] == "accepted"

    # 34 & 35. Late sequence 2 arrives: recorded as 'ignored'; does NOT alter accepted status
    b2, h2 = _build_signed_payload(sub, event_type="lender.declined", sequence_number=2)
    r2 = client.post("/api/v1/webhooks/mock-lenders/events", content=b2, headers=h2)
    assert r2.status_code == 200
    assert r2.json()["processing_status"] == "ignored"
    assert r2.json()["submission_status"] == "accepted"

    db_session.refresh(sub)
    assert sub.status == "accepted"

    # 36. Different event ID with already processed sequence (3) is also ignored
    b3_alt, h3_alt = _build_signed_payload(sub, event_type="lender.declined", sequence_number=3)
    r3_alt = client.post("/api/v1/webhooks/mock-lenders/events", content=b3_alt, headers=h3_alt)
    assert r3_alt.status_code == 200
    assert r3_alt.json()["processing_status"] == "ignored"
    assert r3_alt.json()["submission_status"] == "accepted"

    # 37. Higher sequence 4 arrives: can correct earlier outcome
    b4, h4 = _build_signed_payload(sub, event_type="lender.failed", sequence_number=4)
    r4 = client.post("/api/v1/webhooks/mock-lenders/events", content=b4, headers=h4)
    assert r4.status_code == 200
    assert r4.json()["processing_status"] == "processed"
    assert r4.json()["submission_status"] == "failed"

    db_session.refresh(sub)
    assert sub.status == "failed"


# --- 6. Failure and Transaction Handling (Cases 39-42) ---


def test_database_error_rolls_back_event_and_outcome(
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Cases 39, 40, 41, 42: Transaction failure rolls back all event and status changes; permits retry."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)

    fixed_event_id = f"evt_fail_{uuid.uuid4()}"
    event = MockLenderWebhookEvent(
        event_id=fixed_event_id,
        submission_id=sub.id,
        mock_reference=sub.mock_reference,
        lender_code="APEX_FINANCIAL",
        event_type="lender.accepted",
        sequence_number=1,
        occurred_at=datetime.now(timezone.utc),
    )

    # 40. Simulate DB commit error
    with patch.object(db_session, "commit", side_effect=RuntimeError("Simulated DB failure")):
        with pytest.raises(RuntimeError):
            process_mock_lender_event(db=db_session, event=event)

    # 39 & 42. Verify rollback: submission status remains 'submitted', event row not persisted
    db_session.rollback()
    db_session.refresh(sub)
    assert sub.status == "submitted"
    assert db_session.query(LenderEvent).filter(LenderEvent.event_id == fixed_event_id).count() == 0

    # 41. Retrying same event now succeeds once DB recovers
    res = process_mock_lender_event(db=db_session, event=event)
    assert res.processing_status == "processed"
    assert res.submission_status == "accepted"
    db_session.refresh(sub)
    assert sub.status == "accepted"


# --- 7. Event History API (Cases 43-50) ---


def test_customer_event_history_api(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
    event_customer_b: Tuple[User, str],
    event_caller: Tuple[User, str],
    event_admin: Tuple[User, str],
) -> None:
    """Cases 43, 44, 45, 46, 47, 48, 49, 50: Event history queries, deterministic sorting, and RBAC."""
    user_a, token_a = event_customer_a
    user_b, token_b = event_customer_b
    caller_user, caller_token = event_caller
    admin_user, admin_token = event_admin

    app, offer, sub = _create_submitted_application(db_session, user_a.id)

    # Send sequence 1 and sequence 2
    b1, h1 = _build_signed_payload(sub, event_type="lender.accepted", sequence_number=1)
    b2, h2 = _build_signed_payload(sub, event_type="lender.declined", sequence_number=2)
    client.post("/api/v1/webhooks/mock-lenders/events", content=b1, headers=h1)
    client.post("/api/v1/webhooks/mock-lenders/events", content=b2, headers=h2)

    # 43 & 44. Customer A retrieves history sorted deterministically by sequence_number
    resp = client.get(
        f"/api/v1/applications/{app.id}/submission/events",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    events_data = resp.json()
    assert len(events_data) == 2
    assert events_data[0]["sequence_number"] == 1
    assert events_data[1]["sequence_number"] == 2
    assert events_data[0]["event_type"] == "lender.accepted"
    assert events_data[1]["event_type"] == "lender.declined"

    # 50. Event history contains no PII or signatures
    for item in events_data:
        assert "signature" not in item
        assert "secret" not in item
        assert "customer" not in str(item)

    # 45. Customer B cannot see Customer A's event history -> 404
    r_cust_b = client.get(
        f"/api/v1/applications/{app.id}/submission/events",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_cust_b.status_code == 404

    # 46. Caller -> 403
    r_caller = client.get(
        f"/api/v1/applications/{app.id}/submission/events",
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    assert r_caller.status_code == 403

    # 47. Admin -> 403
    r_admin = client.get(
        f"/api/v1/applications/{app.id}/submission/events",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_admin.status_code == 403

    # 48. Missing auth -> 401
    r_unauth = client.get(f"/api/v1/applications/{app.id}/submission/events")
    assert r_unauth.status_code == 401

    # 49. Application without a submission returns empty list
    app_no_sub = LoanApplication(
        customer_id=user_a.id,
        age=25,
        monthly_income=Decimal("50000.00"),
        work_type="salaried",
        requested_amount=Decimal("100000.00"),
        status="draft",
    )
    db_session.add(app_no_sub)
    db_session.commit()
    r_empty = client.get(
        f"/api/v1/applications/{app_no_sub.id}/submission/events",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r_empty.status_code == 200
    assert r_empty.json() == []


# --- 8. Idempotency Interaction (Cases 51-53) ---


def test_submission_replay_after_webhook_outcome(
    client: TestClient,
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Cases 51, 52, 53: Replaying original offer submission returns existing status and creates no events."""
    user, token = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)
    idemp_key = sub.idempotency_key

    # Webhook processes 'lender.accepted'
    b, h = _build_signed_payload(sub, event_type="lender.accepted", sequence_number=1)
    r_hook = client.post("/api/v1/webhooks/mock-lenders/events", content=b, headers=h)
    assert r_hook.status_code == 200

    events_before = db_session.query(LenderEvent).filter(LenderEvent.submission_id == sub.id).count()
    assert events_before == 1

    # 51 & 52. Client replays original submission request
    r_sub = client.post(
        f"/api/v1/applications/{app.id}/offers/{offer.id}/submit",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idemp_key},
    )
    assert r_sub.status_code == 200
    d_sub = r_sub.json()
    assert d_sub["submission_result"] == "replayed"
    assert d_sub["status"] == "accepted"  # Preserves accepted status!

    # 53. No new events created
    events_after = db_session.query(LenderEvent).filter(LenderEvent.submission_id == sub.id).count()
    assert events_after == events_before


# --- 9. Concurrency Tests (Cases 54-56) ---


def test_concurrency_serializes_and_prevents_duplicate_events(
    db_session: Session,
    setup_event_policies: None,
    event_customer_a: Tuple[User, str],
) -> None:
    """Cases 54, 55, 56: Multi-threaded delivery tests concurrency serialization and duplicate prevention."""
    user, _ = event_customer_a
    app, offer, sub = _create_submitted_application(db_session, user.id)

    fixed_event_id = f"evt_concurrent_{uuid.uuid4()}"
    fixed_time = datetime.now(timezone.utc)

    # 56. Concurrent deliveries of the exact same event_id across separate database sessions
    results = []
    errors = []

    def run_delivery() -> None:
        local_session = SessionLocal()
        try:
            evt = MockLenderWebhookEvent(
                event_id=fixed_event_id,
                submission_id=sub.id,
                mock_reference=sub.mock_reference,
                lender_code="APEX_FINANCIAL",
                event_type="lender.accepted",
                sequence_number=1,
                occurred_at=fixed_time,
            )
            res = process_mock_lender_event(db=local_session, event=evt)
            results.append(res)
        except Exception as e:
            errors.append(e)
        finally:
            local_session.close()

    t1 = threading.Thread(target=run_delivery)
    t2 = threading.Thread(target=run_delivery)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # One delivery succeeded as new, and the other succeeded as duplicate replay (or re-queried)
    assert len(results) == 2
    assert len(errors) == 0

    duplicates = [r.duplicate for r in results]
    assert True in duplicates  # At least one was identified as duplicate

    # Exactly 1 row persisted in PostgreSQL
    count = db_session.query(LenderEvent).filter(LenderEvent.event_id == fixed_event_id).count()
    assert count == 1


# --- 10. Test Cleanup Safety (Case 57) ---


def test_unrelated_submission_and_event_survive_cleanup(
    db_session: Session,
    setup_event_policies: None,
) -> None:
    """Case 57: Ensure test cleanup does not delete unrelated non-test submissions or events."""
    # Clean any stale unrelated customer from previous aborted run
    stale_users = db_session.query(User).filter(User.email.like("unrelated_real_customer%@example.com")).all()
    for su in stale_users:
        app_ids = [a[0] for a in db_session.query(LoanApplication.id).filter(LoanApplication.customer_id == su.id).all()]
        if app_ids:
            db_session.query(LenderEvent).filter(
                LenderEvent.submission_id.in_(
                    db_session.query(OfferSubmission.id).filter(OfferSubmission.application_id.in_(app_ids))
                )
            ).delete(synchronize_session=False)
            db_session.query(OfferSubmission).filter(OfferSubmission.application_id.in_(app_ids)).delete(synchronize_session=False)
            run_ids = [r[0] for r in db_session.query(MatchRun.id).filter(MatchRun.application_id.in_(app_ids)).all()]
            if run_ids:
                dec_ids = [d[0] for d in db_session.query(LenderDecision.id).filter(LenderDecision.match_run_id.in_(run_ids)).all()]
                if dec_ids:
                    db_session.query(Offer).filter(Offer.lender_decision_id.in_(dec_ids)).delete(synchronize_session=False)
                    db_session.query(LenderDecision).filter(LenderDecision.id.in_(dec_ids)).delete(synchronize_session=False)
                db_session.query(MatchRun).filter(MatchRun.id.in_(run_ids)).delete(synchronize_session=False)
            db_session.query(Consent).filter(Consent.application_id.in_(app_ids)).delete(synchronize_session=False)
            db_session.query(LoanApplication).filter(LoanApplication.id.in_(app_ids)).delete(synchronize_session=False)
        db_session.delete(su)
    db_session.commit()

    # Create an unrelated user without test prefix
    unrelated_email = f"unrelated_real_customer_{uuid.uuid4().hex[:8]}@example.com"
    unrelated_user = User(
        full_name="Unrelated Real Customer",
        email=unrelated_email,
        password_hash="dummy_hash_12345678",
        role="customer",
        is_active=True,
    )
    db_session.add(unrelated_user)
    db_session.commit()
    db_session.refresh(unrelated_user)

    try:
        app, off, sub = _create_submitted_application(db_session, unrelated_user.id)

        evt = LenderEvent(
            submission_id=sub.id,
            event_id=f"evt_unrelated_{uuid.uuid4()}",
            event_type="lender.accepted",
            sequence_number=1,
            event_payload={"simulation": True},
            processing_status="processed",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(evt)
        db_session.commit()

        # Run cleanup of event test records
        _clean_event_test_records(db_session)

        # Verify unrelated record survived intact
        assert db_session.query(OfferSubmission).filter(OfferSubmission.id == sub.id).count() == 1
        assert db_session.query(LenderEvent).filter(LenderEvent.id == evt.id).count() == 1
    finally:
        # Cleanup this specific dummy user afterwards
        app_ids = [a[0] for a in db_session.query(LoanApplication.id).filter(LoanApplication.customer_id == unrelated_user.id).all()]
        if app_ids:
            db_session.query(LenderEvent).filter(
                LenderEvent.submission_id.in_(
                    db_session.query(OfferSubmission.id).filter(OfferSubmission.application_id.in_(app_ids))
                )
            ).delete(synchronize_session=False)
            db_session.query(OfferSubmission).filter(OfferSubmission.application_id.in_(app_ids)).delete(synchronize_session=False)
            run_ids = [r[0] for r in db_session.query(MatchRun.id).filter(MatchRun.application_id.in_(app_ids)).all()]
            if run_ids:
                dec_ids = [d[0] for d in db_session.query(LenderDecision.id).filter(LenderDecision.match_run_id.in_(run_ids)).all()]
                if dec_ids:
                    db_session.query(Offer).filter(Offer.lender_decision_id.in_(dec_ids)).delete(synchronize_session=False)
                    db_session.query(LenderDecision).filter(LenderDecision.id.in_(dec_ids)).delete(synchronize_session=False)
                db_session.query(MatchRun).filter(MatchRun.id.in_(run_ids)).delete(synchronize_session=False)
            db_session.query(Consent).filter(Consent.application_id.in_(app_ids)).delete(synchronize_session=False)
            db_session.query(LoanApplication).filter(LoanApplication.id.in_(app_ids)).delete(synchronize_session=False)
        db_session.delete(unrelated_user)
        db_session.commit()
