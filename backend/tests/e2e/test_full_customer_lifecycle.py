import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.webhook_security import create_mock_webhook_signature
from app.models.lender_event import LenderEvent
from app.models.loan_application import LoanApplication
from app.models.offer import Offer
from app.models.offer_submission import OfferSubmission
from tests.e2e.conftest import E2E_CUST_PREFIX, E2E_WEBHOOK_SECRET


def _build_signed_webhook(
    submission_id: int,
    mock_reference: str,
    lender_code: str,
    event_type: str,
    sequence_number: int,
    event_id: str = None,
    secret: str = E2E_WEBHOOK_SECRET,
    reason_code: str = None,
) -> Tuple[bytes, Dict[str, str]]:
    """Helper to build raw signed webhook payload and headers."""
    if event_id is None:
        event_id = f"evt_{uuid.uuid4()}"

    payload_dict = {
        "event_id": event_id,
        "submission_id": submission_id,
        "mock_reference": mock_reference,
        "lender_code": lender_code,
        "event_type": event_type,
        "sequence_number": sequence_number,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    if reason_code:
        payload_dict["reason_code"] = reason_code

    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = create_mock_webhook_signature(raw_bytes, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Mock-Lender-Signature": sig,
    }
    return raw_bytes, headers


def test_complete_customer_lifecycle_and_acceptance(
    client: TestClient,
    db_session: Session,
) -> None:
    """Full 28-step customer journey from registration to terminal acceptance and audit."""

    # -------------------------------------------------------------
    # Step 1: Register a fictional customer
    # -------------------------------------------------------------
    customer_email = f"{E2E_CUST_PREFIX}journey_{uuid.uuid4().hex[:8]}@example.com"
    customer_password = "E2eSecurePassword123!"

    reg_payload = {
        "full_name": "E2E Fictional Customer",
        "email": customer_email,
        "password": customer_password,
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    reg_data = reg_resp.json()
    assert reg_data["email"] == customer_email
    assert reg_data["role"] == "customer"
    assert "id" in reg_data

    # -------------------------------------------------------------
    # Step 2: Log in
    # -------------------------------------------------------------
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": customer_email, "password": customer_password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    login_data = login_resp.json()
    token = login_data["access_token"]
    assert token, "Token must be returned"
    headers = {"Authorization": f"Bearer {token}"}

    # -------------------------------------------------------------
    # Step 3: Retrieve /auth/me
    # -------------------------------------------------------------
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == customer_email
    assert me_data["role"] == "customer"
    assert me_data["full_name"] == "E2E Fictional Customer"

    # -------------------------------------------------------------
    # Step 4: Create a loan application
    # -------------------------------------------------------------
    app_payload = {
        "requested_amount": "50000.00",
        "monthly_income": "60000.00",
        "age": 29,
        "work_type": "salaried",
    }
    create_app_resp = client.post("/api/v1/applications/", json=app_payload, headers=headers)
    assert create_app_resp.status_code == 201
    app_data = create_app_resp.json()
    application_id = app_data["id"]
    assert app_data["status"] == "draft"

    # -------------------------------------------------------------
    # Step 5: Read current consent notices
    # -------------------------------------------------------------
    notices_resp = client.get("/api/v1/consents/notices", headers=headers)
    assert notices_resp.status_code == 200
    notices = notices_resp.json()
    assert len(notices) >= 2
    purposes = {n["purpose"] for n in notices}
    assert "eligibility_matching" in purposes
    assert "sharing_with_mock_lenders" in purposes

    # -------------------------------------------------------------
    # Step 6: Grant eligibility_matching consent
    # -------------------------------------------------------------
    grant_resp_1 = client.post(
        f"/api/v1/applications/{application_id}/consents",
        json={"purpose": "eligibility_matching", "notice_version": "v1.0", "accepted": True},
        headers=headers,
    )
    assert grant_resp_1.status_code == 201
    assert grant_resp_1.json()["status"] == "granted"

    # -------------------------------------------------------------
    # Step 7: Grant sharing_with_mock_lenders consent separately
    # -------------------------------------------------------------
    grant_resp_2 = client.post(
        f"/api/v1/applications/{application_id}/consents",
        json={"purpose": "sharing_with_mock_lenders", "notice_version": "v1.0", "accepted": True},
        headers=headers,
    )
    assert grant_resp_2.status_code == 201
    assert grant_resp_2.json()["status"] == "granted"

    # -------------------------------------------------------------
    # Step 8: Run matching
    # -------------------------------------------------------------
    match_resp = client.post(
        f"/api/v1/applications/{application_id}/match",
        headers=headers,
    )
    assert match_resp.status_code == 201, f"Matching failed: {match_resp.text}"
    match_data = match_resp.json()
    assert "id" in match_data

    # -------------------------------------------------------------
    # Step 9: Verify three configured fictional lender decisions are returned
    # -------------------------------------------------------------
    decisions = match_data["decisions"]
    assert len(decisions) == 3
    lender_codes = {d["lender_code"] for d in decisions}
    assert lender_codes == {"APEX_FINANCIAL", "HORIZON_CREDIT", "STERLING_LOANS"}
    eligible_decisions = [d for d in decisions if d["decision_status"] == "eligible"]
    assert len(eligible_decisions) >= 1

    # -------------------------------------------------------------
    # Step 10: Generate offers
    # -------------------------------------------------------------
    gen_offers_resp = client.post(
        f"/api/v1/applications/{application_id}/offers/generate",
        headers=headers,
    )
    assert gen_offers_resp.status_code == 200
    gen_data = gen_offers_resp.json()
    assert gen_data["generated_count"] >= 1
    assert len(gen_data["offers"]) >= 1

    # -------------------------------------------------------------
    # Step 11: Retrieve offers
    # -------------------------------------------------------------
    offers_resp = client.get(
        f"/api/v1/applications/{application_id}/offers",
        headers=headers,
    )
    assert offers_resp.status_code == 200
    offers = offers_resp.json()
    assert len(offers) == len(gen_data["offers"])
    chosen_offer = offers[0]
    chosen_offer_id = chosen_offer["id"]
    original_apr = Decimal(str(chosen_offer["apr"]))
    original_amount = Decimal(str(chosen_offer["loan_amount"]))

    # -------------------------------------------------------------
    # Step 12: Retrieve mock KFS
    # -------------------------------------------------------------
    kfs_resp = client.get(
        f"/api/v1/applications/{application_id}/offers/{chosen_offer_id}/kfs",
        headers=headers,
    )
    assert kfs_resp.status_code == 200
    kfs_data = kfs_resp.json()
    assert "nominal_annual_apr_percent" in kfs_data
    assert "estimated_total_repayment" in kfs_data
    assert "monthly_installment" in kfs_data
    assert "training_disclosure" in kfs_data

    # -------------------------------------------------------------
    # Step 13: Select exactly one offer
    # -------------------------------------------------------------
    select_resp = client.post(
        f"/api/v1/applications/{application_id}/offers/{chosen_offer_id}/select",
        headers=headers,
    )
    assert select_resp.status_code == 200
    select_data = select_resp.json()
    assert select_data["selected_offer"]["status"] == "selected"

    # -------------------------------------------------------------
    # Step 14: Verify alternative offers are withdrawn
    # -------------------------------------------------------------
    offers_after_select_resp = client.get(
        f"/api/v1/applications/{application_id}/offers",
        headers=headers,
    )
    for off in offers_after_select_resp.json():
        if off["id"] == chosen_offer_id:
            assert off["status"] == "selected"
        else:
            assert off["status"] == "withdrawn"

    # -------------------------------------------------------------
    # Step 15: Submit selected offer with Idempotency-Key
    # -------------------------------------------------------------
    idempotency_key = str(uuid.uuid4())
    sub_headers = {
        **headers,
        "Idempotency-Key": idempotency_key,
    }
    sub_resp = client.post(
        f"/api/v1/applications/{application_id}/offers/{chosen_offer_id}/submit",
        headers=sub_headers,
    )
    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    submission_id = sub_data["id"]
    mock_reference = sub_data["mock_reference"]
    assert sub_data["status"] == "submitted"
    assert sub_data["application_id"] == application_id
    assert sub_data["offer_id"] == chosen_offer_id

    # -------------------------------------------------------------
    # Step 16: Verify one OfferSubmission is created in DB
    # -------------------------------------------------------------
    db_session.expire_all()
    submissions = (
        db_session.query(OfferSubmission)
        .filter(OfferSubmission.application_id == application_id)
        .all()
    )
    assert len(submissions) == 1
    assert submissions[0].idempotency_key == idempotency_key

    # -------------------------------------------------------------
    # Step 17: Replay submission using same key
    # -------------------------------------------------------------
    replay_sub_resp = client.post(
        f"/api/v1/applications/{application_id}/offers/{chosen_offer_id}/submit",
        headers=sub_headers,
    )
    assert replay_sub_resp.status_code == 200
    replay_sub_data = replay_sub_resp.json()
    assert replay_sub_data["id"] == submission_id
    assert replay_sub_data["mock_reference"] == mock_reference
    assert replay_sub_data["submission_result"] == "replayed"

    # -------------------------------------------------------------
    # Step 18: Verify no duplicate submission in DB
    # -------------------------------------------------------------
    db_session.expire_all()
    submissions_after_replay = (
        db_session.query(OfferSubmission)
        .filter(OfferSubmission.application_id == application_id)
        .all()
    )
    assert len(submissions_after_replay) == 1

    # -------------------------------------------------------------
    # Step 19: Generate a valid HMAC-signed lender.accepted event
    # -------------------------------------------------------------
    event_id = f"evt_{uuid.uuid4()}"
    raw_webhook, webhook_headers = _build_signed_webhook(
        submission_id=submission_id,
        mock_reference=mock_reference,
        lender_code="APEX_FINANCIAL",
        event_type="lender.accepted",
        sequence_number=2,
        event_id=event_id,
    )

    # -------------------------------------------------------------
    # Step 20: Process the event
    # -------------------------------------------------------------
    webhook_resp = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=raw_webhook,
        headers=webhook_headers,
    )
    assert webhook_resp.status_code == 200
    wh_data = webhook_resp.json()
    assert wh_data["processing_status"] == "processed"
    assert wh_data["submission_status"] == "accepted"
    assert wh_data["application_status"] == "accepted"
    assert wh_data["duplicate"] is False

    # -------------------------------------------------------------
    # Step 21: Replay exact event
    # -------------------------------------------------------------
    replay_wh_resp = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=raw_webhook,
        headers=webhook_headers,
    )
    assert replay_wh_resp.status_code == 200
    replay_wh_data = replay_wh_resp.json()
    assert replay_wh_data["duplicate"] is True

    # -------------------------------------------------------------
    # Step 22: Verify no duplicate event row in DB
    # -------------------------------------------------------------
    db_session.expire_all()
    event_rows = (
        db_session.query(LenderEvent)
        .filter(LenderEvent.submission_id == submission_id)
        .all()
    )
    assert len(event_rows) == 1
    assert event_rows[0].event_id == event_id

    # -------------------------------------------------------------
    # Step 23: Send a stale lower-sequence event
    # -------------------------------------------------------------
    stale_event_id = f"evt_{uuid.uuid4()}"
    stale_raw_webhook, stale_webhook_headers = _build_signed_webhook(
        submission_id=submission_id,
        mock_reference=mock_reference,
        lender_code="APEX_FINANCIAL",
        event_type="lender.declined",
        sequence_number=1,  # Lower sequence (1 < 2)
        event_id=stale_event_id,
    )
    stale_wh_resp = client.post(
        "/api/v1/webhooks/mock-lenders/events",
        content=stale_raw_webhook,
        headers=stale_webhook_headers,
    )
    assert stale_wh_resp.status_code == 200
    stale_wh_data = stale_wh_resp.json()

    # -------------------------------------------------------------
    # Step 24: Verify it is ignored
    # -------------------------------------------------------------
    assert stale_wh_data["processing_status"] == "ignored"

    # -------------------------------------------------------------
    # Step 25: Verify application and submission remain accepted
    # -------------------------------------------------------------
    db_session.expire_all()
    app_in_db = db_session.get(LoanApplication, application_id)
    sub_in_db = db_session.get(OfferSubmission, submission_id)
    assert app_in_db.status == "accepted"
    assert sub_in_db.status == "accepted"

    # -------------------------------------------------------------
    # Step 26: Retrieve submission event history
    # -------------------------------------------------------------
    history_resp = client.get(
        f"/api/v1/applications/{application_id}/submission/events",
        headers=headers,
    )
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) >= 1
    assert any(evt["event_type"] == "lender.accepted" for evt in history)

    # -------------------------------------------------------------
    # Step 27: Retrieve KFS after terminal outcome
    # -------------------------------------------------------------
    terminal_kfs_resp = client.get(
        f"/api/v1/applications/{application_id}/offers/{chosen_offer_id}/kfs",
        headers=headers,
    )
    assert terminal_kfs_resp.status_code == 200
    terminal_kfs_data = terminal_kfs_resp.json()
    assert Decimal(str(terminal_kfs_data["nominal_annual_apr_percent"])) == original_apr

    # -------------------------------------------------------------
    # Step 28: Verify saved Offer financial terms remain unchanged
    # -------------------------------------------------------------
    db_session.expire_all()
    offer_in_db = db_session.get(Offer, chosen_offer_id)
    assert offer_in_db.apr == original_apr
    assert offer_in_db.loan_amount == original_amount


# ===========================================================================
# Terminal Outcome Tests: declined, timed_out, failed
# ===========================================================================


def _setup_independent_submission(
    client: TestClient,
    prefix_suffix: str,
) -> Tuple[str, int, int, str]:
    """Helper to set up a new application through offer submission."""
    email = f"{E2E_CUST_PREFIX}term_{prefix_suffix}_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "E2eSecurePassword123!"

    client.post("/api/v1/auth/register", json={"full_name": "Terminal Test", "email": email, "password": pwd})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": pwd}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Application
    app_id = client.post(
        "/api/v1/applications/",
        json={"requested_amount": "50000.00", "monthly_income": "60000.00", "age": 28, "work_type": "salaried"},
        headers=headers,
    ).json()["id"]

    # Consents
    client.post(
        f"/api/v1/applications/{app_id}/consents",
        json={"purpose": "eligibility_matching", "notice_version": "v1.0", "accepted": True},
        headers=headers,
    )
    client.post(
        f"/api/v1/applications/{app_id}/consents",
        json={"purpose": "sharing_with_mock_lenders", "notice_version": "v1.0", "accepted": True},
        headers=headers,
    )

    # Match & Offers
    client.post(f"/api/v1/applications/{app_id}/match", headers=headers)
    offers_data = client.post(f"/api/v1/applications/{app_id}/offers/generate", headers=headers).json()
    offer_id = offers_data["offers"][0]["id"]

    # Select & Submit
    client.post(f"/api/v1/applications/{app_id}/offers/{offer_id}/select", headers=headers)
    sub = client.post(
        f"/api/v1/applications/{app_id}/offers/{offer_id}/submit",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    ).json()

    return headers["Authorization"], app_id, sub["id"], sub["mock_reference"]


def test_independent_application_terminal_declined(
    client: TestClient,
    db_session: Session,
) -> None:
    """Terminal outcome verification: lender.declined."""
    auth_header, app_id, sub_id, mock_ref = _setup_independent_submission(client, "declined")

    raw_wh, headers = _build_signed_webhook(
        submission_id=sub_id,
        mock_reference=mock_ref,
        lender_code="APEX_FINANCIAL",
        event_type="lender.declined",
        sequence_number=1,
        reason_code="CREDIT_POLICY_THRESHOLD",
    )
    resp = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_wh, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["submission_status"] == "declined"
    assert data["application_status"] == "declined"

    db_session.expire_all()
    assert db_session.get(LoanApplication, app_id).status == "declined"
    assert db_session.get(OfferSubmission, sub_id).status == "declined"


def test_independent_application_terminal_timed_out(
    client: TestClient,
    db_session: Session,
) -> None:
    """Terminal outcome verification: lender.timed_out."""
    auth_header, app_id, sub_id, mock_ref = _setup_independent_submission(client, "timed_out")

    raw_wh, headers = _build_signed_webhook(
        submission_id=sub_id,
        mock_reference=mock_ref,
        lender_code="APEX_FINANCIAL",
        event_type="lender.timed_out",
        sequence_number=1,
        reason_code="SIMULATED_TIMEOUT",
    )
    resp = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_wh, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["submission_status"] == "timed_out"
    assert data["application_status"] == "timed_out"

    db_session.expire_all()
    assert db_session.get(LoanApplication, app_id).status == "timed_out"
    assert db_session.get(OfferSubmission, sub_id).status == "timed_out"


def test_independent_application_terminal_failed(
    client: TestClient,
    db_session: Session,
) -> None:
    """Terminal outcome verification: lender.failed."""
    auth_header, app_id, sub_id, mock_ref = _setup_independent_submission(client, "failed")

    raw_wh, headers = _build_signed_webhook(
        submission_id=sub_id,
        mock_reference=mock_ref,
        lender_code="APEX_FINANCIAL",
        event_type="lender.failed",
        sequence_number=1,
        reason_code="ADAPTER_COMMUNICATION_ERROR",
    )
    resp = client.post("/api/v1/webhooks/mock-lenders/events", content=raw_wh, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["submission_status"] == "failed"
    assert data["application_status"] == "failed"

    db_session.expire_all()
    assert db_session.get(LoanApplication, app_id).status == "failed"
    assert db_session.get(OfferSubmission, sub_id).status == "failed"
