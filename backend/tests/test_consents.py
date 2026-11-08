from datetime import datetime, timezone
from decimal import Decimal
from typing import Tuple

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.models.loan_application import LoanApplication
from app.models.user import User
from app.services.consent_notices import (
    CURRENT_NOTICE_VERSIONS,
    PURPOSE_ELIGIBILITY_MATCHING,
    PURPOSE_SHARING_WITH_MOCK_LENDERS,
)
from app.services.consent_service import (
    ALLOWED_CONSENT_APPLICATION_STATUSES,
    get_missing_required_consents,
    has_required_active_consents,
    is_consent_change_permitted,
)


def _create_draft_application(db: Session, customer_id: int) -> LoanApplication:
    """Helper to create a draft application for a given customer."""
    app = LoanApplication(
        customer_id=customer_id,
        age=30,
        monthly_income=Decimal("60000.00"),
        work_type="salaried",
        requested_amount=Decimal("200000.00"),
        status="draft",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


# ==============================================================================
# Notice Registry Tests (1–6)
# ==============================================================================


def test_customer_can_retrieve_current_consent_notices(
    client: TestClient,
    consent_customer_a: Tuple[User, str],
):
    """1. Customer can retrieve current consent notices."""
    _, token = consent_customer_a
    response = client.get(
        "/api/v1/consents/notices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    notices = response.json()
    assert len(notices) >= 2


def test_both_required_purposes_present_in_notices(
    client: TestClient,
    consent_customer_a: Tuple[User, str],
):
    """2. Both required purposes are present in notice response."""
    _, token = consent_customer_a
    response = client.get(
        "/api/v1/consents/notices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    purposes = {n["purpose"] for n in response.json()}
    assert PURPOSE_ELIGIBILITY_MATCHING in purposes
    assert PURPOSE_SHARING_WITH_MOCK_LENDERS in purposes


def test_notice_versions_are_returned(
    client: TestClient,
    consent_customer_a: Tuple[User, str],
):
    """3. Notice versions are returned for each notice."""
    _, token = consent_customer_a
    response = client.get(
        "/api/v1/consents/notices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    for n in response.json():
        assert n["notice_version"] == "v1.0"
        assert n["required_for_matching"] is True


def test_notice_wording_identifies_mock_environment(
    client: TestClient,
    consent_customer_a: Tuple[User, str],
):
    """4. Notice wording clearly identifies the training-only mock environment."""
    _, token = consent_customer_a
    response = client.get(
        "/api/v1/consents/notices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    for n in response.json():
        text = n["notice_text"].lower()
        assert "no real lender" in text
        assert "no real credit bureau" in text
        assert "no real otp" in text


def test_caller_and_admin_cannot_access_consent_endpoints(
    client: TestClient,
    rbac_caller_a: Tuple[User, str],
    rbac_admin: Tuple[User, str],
):
    """5. Caller and Admin cannot access customer consent endpoints (403)."""
    _, caller_token = rbac_caller_a
    _, admin_token = rbac_admin

    resp_caller = client.get(
        "/api/v1/consents/notices",
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    assert resp_caller.status_code == 403

    resp_admin = client.get(
        "/api/v1/consents/notices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 403


def test_missing_token_returns_401_on_consent_endpoints(client: TestClient):
    """6. Missing token returns HTTP 401 with WWW-Authenticate header."""
    response = client.get("/api/v1/consents/notices")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


# ==============================================================================
# Consent Grant Tests (7–20)
# ==============================================================================


def test_customer_can_grant_eligibility_matching_consent(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """7. Customer can grant eligibility-matching consent (201)."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    payload = {
        "purpose": PURPOSE_ELIGIBILITY_MATCHING,
        "notice_version": CURRENT_NOTICE_VERSIONS[PURPOSE_ELIGIBILITY_MATCHING],
        "accepted": True,
    }
    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["purpose"] == PURPOSE_ELIGIBILITY_MATCHING
    assert data["notice_version"] == "v1.0"
    assert data["status"] == "granted"


def test_customer_can_grant_mock_lender_sharing_consent(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """8. Customer can grant mock-lender-sharing consent (201)."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    payload = {
        "purpose": PURPOSE_SHARING_WITH_MOCK_LENDERS,
        "notice_version": CURRENT_NOTICE_VERSIONS[PURPOSE_SHARING_WITH_MOCK_LENDERS],
        "accepted": True,
    }
    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["purpose"] == PURPOSE_SHARING_WITH_MOCK_LENDERS


def test_correct_application_id_is_stored(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """9. Correct application_id is stored in consent record."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    payload = {
        "purpose": PURPOSE_ELIGIBILITY_MATCHING,
        "notice_version": "v1.0",
        "accepted": True,
    }
    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["application_id"] == app.id


def test_correct_purpose_and_notice_version_are_stored(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """10. Correct purpose and notice version are stored in the database."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_SHARING_WITH_MOCK_LENDERS, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    consent_id = response.json()["id"]

    db_consent = db_session.get(Consent, consent_id)
    assert db_consent is not None
    assert db_consent.purpose == PURPOSE_SHARING_WITH_MOCK_LENDERS
    assert db_consent.notice_version == "v1.0"


def test_consent_status_is_granted(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """11. Consent status is 'granted'."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "granted"


def test_granted_at_is_populated_and_revoked_at_is_null(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """12. granted_at is populated and revoked_at is NULL on new grant."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["granted_at"] is not None
    assert data["revoked_at"] is None


def test_different_customer_application_returns_404(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
    consent_customer_b: Tuple[User, str],
):
    """13. A different customer's application returns HTTP 404."""
    user_a, _ = consent_customer_a
    _, token_b = consent_customer_b
    app_a = _create_draft_application(db_session, user_a.id)

    response = client.post(
        f"/api/v1/applications/{app_a.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Loan application not found."


def test_unknown_application_returns_404(
    client: TestClient,
    consent_customer_a: Tuple[User, str],
):
    """14. Unknown application returns HTTP 404."""
    _, token = consent_customer_a
    response = client.post(
        "/api/v1/applications/99999999/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Loan application not found."


def test_unsupported_purpose_is_rejected(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """15. Unsupported purpose is rejected with HTTP 422."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": "marketing_newsletter", "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_unknown_or_outdated_notice_version_is_rejected(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """16. Unknown or outdated notice version is rejected with HTTP 422."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v99.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_accepted_false_is_rejected(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """17. accepted=false is rejected with HTTP 422 and creates no record."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    response = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    count = db_session.query(Consent).filter(Consent.application_id == app.id).count()
    assert count == 0


def test_repeated_grant_is_idempotent(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """18. Repeated grant of an active same-version consent is idempotent (returns 200)."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    payload = {"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True}
    resp1 = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201
    c1_id = resp1.json()["id"]

    resp2 = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == c1_id


def test_duplicate_grant_does_not_create_duplicate_record(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """19. Duplicate grant does not create duplicate record in DB."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    payload = {"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True}
    client.post(f"/api/v1/applications/{app.id}/consents", json=payload, headers={"Authorization": f"Bearer {token}"})
    client.post(f"/api/v1/applications/{app.id}/consents", json=payload, headers={"Authorization": f"Bearer {token}"})

    count = db_session.query(Consent).filter(Consent.application_id == app.id).count()
    assert count == 1


def test_regrant_of_revoked_same_version_returns_409(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """20. Re-grant of a revoked same-version consent returns HTTP 409 Conflict."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    payload = {"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True}
    resp = client.post(f"/api/v1/applications/{app.id}/consents", json=payload, headers={"Authorization": f"Bearer {token}"})
    consent_id = resp.json()["id"]

    # Revoke consent
    rev_resp = client.post(
        f"/api/v1/applications/{app.id}/consents/{consent_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev_resp.status_code == 200

    # Attempt re-grant on same version
    regrant_resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert regrant_resp.status_code == 409
    assert "previously revoked" in regrant_resp.json()["detail"].lower()


# ==============================================================================
# Consent History Tests (21–24)
# ==============================================================================


def test_customer_can_view_own_consent_history(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """21. Customer can view own application consent history."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_SHARING_WITH_MOCK_LENDERS, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = client.get(
        f"/api/v1/applications/{app.id}/consents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_another_customer_cannot_view_history(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
    consent_customer_b: Tuple[User, str],
):
    """22. Another customer cannot view consent history (404)."""
    user_a, _ = consent_customer_a
    _, token_b = consent_customer_b
    app_a = _create_draft_application(db_session, user_a.id)

    resp = client.get(
        f"/api/v1/applications/{app_a.id}/consents",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Loan application not found."


def test_empty_consent_history_returns_empty_list(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """23. Empty consent history returns empty list []."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    resp = client.get(
        f"/api/v1/applications/{app.id}/consents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_historical_revoked_records_remain_visible(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """24. Historical revoked records remain visible in history."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    grant_resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    consent_id = grant_resp.json()["id"]

    client.post(
        f"/api/v1/applications/{app.id}/consents/{consent_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )

    history_resp = client.get(
        f"/api/v1/applications/{app.id}/consents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history_resp.status_code == 200
    items = history_resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "revoked"
    assert items[0]["revoked_at"] is not None


# ==============================================================================
# Consent Revocation Tests (25–32)
# ==============================================================================


def test_granted_consent_can_be_revoked(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """25. Granted consent can be revoked (HTTP 200)."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    grant_resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    consent_id = grant_resp.json()["id"]

    rev_resp = client.post(
        f"/api/v1/applications/{app.id}/consents/{consent_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "revoked"


def test_revocation_status_changes_to_revoked(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """26. Status changes to revoked in response and database."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = resp.json()["id"]

    client.post(
        f"/api/v1/applications/{app.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    db_c = db_session.get(Consent, cid)
    assert db_c is not None
    assert db_c.status == "revoked"


def test_revoked_at_is_populated_on_revocation(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """27. revoked_at is populated with valid timestamp."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = resp.json()["id"]

    rev_resp = client.post(
        f"/api/v1/applications/{app.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev_resp.json()["revoked_at"] is not None


def test_granted_at_and_version_remain_unchanged_on_revocation(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """28. granted_at and notice_version remain unchanged on revocation."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = resp.json()["id"]
    original_granted_at = resp.json()["granted_at"]

    rev_resp = client.post(
        f"/api/v1/applications/{app.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev_resp.json()["granted_at"] == original_granted_at
    assert rev_resp.json()["notice_version"] == "v1.0"


def test_repeated_revocation_is_idempotent(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """29. Repeated revocation is idempotent and returns HTTP 200."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = resp.json()["id"]

    rev1 = client.post(
        f"/api/v1/applications/{app.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev1.status_code == 200

    rev2 = client.post(
        f"/api/v1/applications/{app.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev2.status_code == 200
    assert rev2.json()["id"] == cid
    assert rev2.json()["status"] == "revoked"


def test_another_customer_consent_cannot_be_revoked(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
    consent_customer_b: Tuple[User, str],
):
    """30. Another customer's consent cannot be revoked (HTTP 404)."""
    user_a, token_a = consent_customer_a
    _, token_b = consent_customer_b
    app_a = _create_draft_application(db_session, user_a.id)

    resp = client.post(
        f"/api/v1/applications/{app_a.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    cid = resp.json()["id"]

    rev_resp = client.post(
        f"/api/v1/applications/{app_a.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert rev_resp.status_code == 404


def test_consent_cannot_be_revoked_after_final_submission(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """31. Consent cannot be revoked after final submission (HTTP 409)."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = resp.json()["id"]

    # Transition application status to submitted
    app.status = "submitted"
    db_session.commit()

    rev_resp = client.post(
        f"/api/v1/applications/{app.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev_resp.status_code == 409
    assert "closed" in rev_resp.json()["detail"].lower()


def test_invalid_pending_to_revoked_transition_rejected(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """32. An invalid pending-to-revoked transition is rejected with HTTP 409."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    # Insert a consent in pending status
    pending_consent = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="pending",
    )
    db_session.add(pending_consent)
    db_session.commit()
    db_session.refresh(pending_consent)

    rev_resp = client.post(
        f"/api/v1/applications/{app.id}/consents/{pending_consent.id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev_resp.status_code == 409


# ==============================================================================
# Matching Readiness Tests (33–37)
# ==============================================================================


def test_no_consent_means_matching_not_ready(db_session: Session, consent_customer_a: Tuple[User, str]):
    """33. No consent means matching is not ready."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    assert has_required_active_consents(db_session, app.id) is False
    missing = get_missing_required_consents(db_session, app.id)
    assert len(missing) == 2


def test_only_one_active_purpose_means_not_ready(db_session: Session, consent_customer_a: Tuple[User, str]):
    """34. Only one active purpose means not ready."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    c1 = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add(c1)
    db_session.commit()

    assert has_required_active_consents(db_session, app.id) is False
    missing = get_missing_required_consents(db_session, app.id)
    assert missing == [PURPOSE_SHARING_WITH_MOCK_LENDERS]


def test_both_active_purposes_means_ready(db_session: Session, consent_customer_a: Tuple[User, str]):
    """35. Both active purposes means ready."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    c1 = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    c2 = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    assert has_required_active_consents(db_session, app.id) is True
    assert get_missing_required_consents(db_session, app.id) == []


def test_revoking_either_purpose_means_not_ready(db_session: Session, consent_customer_a: Tuple[User, str]):
    """36. Revoking either purpose means not ready."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    c1 = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    c2 = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="revoked",
        granted_at=datetime.now(timezone.utc),
        revoked_at=datetime.now(timezone.utc),
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    assert has_required_active_consents(db_session, app.id) is False
    assert get_missing_required_consents(db_session, app.id) == [PURPOSE_SHARING_WITH_MOCK_LENDERS]


def test_old_notice_version_does_not_satisfy_current_requirement(
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """37. Old notice version does not satisfy current notice requirement."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    # Granted under obsolete v0.9 version
    c1 = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v0.9",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    c2 = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    assert has_required_active_consents(db_session, app.id) is False
    assert get_missing_required_consents(db_session, app.id) == [PURPOSE_ELIGIBILITY_MATCHING]


def test_revocation_does_not_delete_consent_row(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """Verify that revocation never deletes the row from the database."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    resp = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = resp.json()["id"]

    client.post(
        f"/api/v1/applications/{app.id}/consents/{cid}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )

    db_row = db_session.get(Consent, cid)
    assert db_row is not None
    assert db_row.status == "revoked"


# ==============================================================================
# Consent Readiness & Lifecycle Regression Tests (Step 8A Hardening)
# ==============================================================================


def test_multiple_granted_notice_versions_correctly_evaluates_readiness(
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """Multiple granted notice versions for one purpose: current version satisfies readiness regardless of older records."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    # Insert old granted version v0.9 and current granted version v1.0
    c_old = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v0.9",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    c_current = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    c_other = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add_all([c_old, c_current, c_other])
    db_session.commit()

    assert has_required_active_consents(db_session, app.id) is True
    assert get_missing_required_consents(db_session, app.id) == []


def test_old_version_does_not_satisfy_current_readiness_even_if_granted(
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """Old granted version does not satisfy current readiness when current version is missing."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    # Only old version v0.9 granted for eligibility_matching
    c_old = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v0.9",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    c_other = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add_all([c_old, c_other])
    db_session.commit()

    assert has_required_active_consents(db_session, app.id) is False
    assert get_missing_required_consents(db_session, app.id) == [PURPOSE_ELIGIBILITY_MATCHING]


def test_revoked_current_version_does_not_satisfy_readiness_despite_old_granted(
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """Revoked current notice version does not satisfy readiness, even if an older version was granted."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    # v0.9 granted, but v1.0 is revoked
    c_old = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v0.9",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    c_revoked = Consent(
        application_id=app.id,
        purpose=PURPOSE_ELIGIBILITY_MATCHING,
        notice_version="v1.0",
        status="revoked",
        granted_at=datetime.now(timezone.utc),
        revoked_at=datetime.now(timezone.utc),
    )
    c_other = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add_all([c_old, c_revoked, c_other])
    db_session.commit()

    assert has_required_active_consents(db_session, app.id) is False
    assert get_missing_required_consents(db_session, app.id) == [PURPOSE_ELIGIBILITY_MATCHING]


def test_missing_purposes_accurately_reported(
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """Missing purposes appear in sorted order in get_missing_required_consents()."""
    user, _ = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    # Both missing
    missing = get_missing_required_consents(db_session, app.id)
    assert missing == [PURPOSE_ELIGIBILITY_MATCHING, PURPOSE_SHARING_WITH_MOCK_LENDERS]

    # Grant only the second purpose
    c2 = Consent(
        application_id=app.id,
        purpose=PURPOSE_SHARING_WITH_MOCK_LENDERS,
        notice_version="v1.0",
        status="granted",
        granted_at=datetime.now(timezone.utc),
    )
    db_session.add(c2)
    db_session.commit()

    missing_after = get_missing_required_consents(db_session, app.id)
    assert missing_after == [PURPOSE_ELIGIBILITY_MATCHING]


def test_unknown_application_status_rejects_consent_modifications(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """Unknown or unexpected application statuses strictly reject consent modification."""
    user, token = consent_customer_a
    app = _create_draft_application(db_session, user.id)

    # Set an unknown status
    app.status = "under_manual_review"
    db_session.commit()

    assert is_consent_change_permitted("under_manual_review") is False
    assert is_consent_change_permitted("unknown_custom_status") is False

    # Attempt to grant consent via API -> 409 Conflict
    resp_grant = client.post(
        f"/api/v1/applications/{app.id}/consents",
        json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_grant.status_code == 409


def test_every_documented_pre_submission_status_allows_consent_changes(
    client: TestClient,
    db_session: Session,
    consent_customer_a: Tuple[User, str],
):
    """All documented pre-submission states allow consent modifications."""
    expected_allowed = {
        "draft",
        "matching",
        "matched",
        "offers_ready",
        "offer_selected",
    }
    assert ALLOWED_CONSENT_APPLICATION_STATUSES == expected_allowed

    user, token = consent_customer_a
    for status in sorted(expected_allowed):
        assert is_consent_change_permitted(status) is True

        app = _create_draft_application(db_session, user.id)
        app.status = status
        db_session.commit()

        # Successfully grant consent
        resp = client.post(
            f"/api/v1/applications/{app.id}/consents",
            json={"purpose": PURPOSE_ELIGIBILITY_MATCHING, "notice_version": "v1.0", "accepted": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201


def test_terminal_and_submitted_statuses_reject_consent_changes():
    """All post-submission and terminal statuses reject consent modifications."""
    terminal_statuses = [
        "submitted",
        "accepted",
        "declined",
        "finalized",
        "timed_out",
        "failed",
    ]
    for status in terminal_statuses:
        assert is_consent_change_permitted(status) is False
