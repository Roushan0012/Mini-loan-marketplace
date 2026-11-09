import uuid
from decimal import Decimal
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.loan_application import LoanApplication
from app.models.user import User
from tests.e2e.conftest import (
    E2E_ADMIN_PREFIX,
    E2E_CALLER_PREFIX,
    E2E_CUST_PREFIX,
    E2E_LEAD_REF_PREFIX,
    create_e2e_lead_with_assignment,
    create_e2e_user,
)


@pytest.fixture
def e2e_customer_a(db_session: Session) -> Tuple[User, str]:
    return create_e2e_user(
        db_session,
        f"{E2E_CUST_PREFIX}user_a_{uuid.uuid4().hex[:6]}@example.com",
        "customer",
        "E2E Customer A",
    )


@pytest.fixture
def e2e_customer_b(db_session: Session) -> Tuple[User, str]:
    return create_e2e_user(
        db_session,
        f"{E2E_CUST_PREFIX}user_b_{uuid.uuid4().hex[:6]}@example.com",
        "customer",
        "E2E Customer B",
    )


@pytest.fixture
def e2e_caller_a(db_session: Session) -> Tuple[User, str]:
    return create_e2e_user(
        db_session,
        f"{E2E_CALLER_PREFIX}caller_a_{uuid.uuid4().hex[:6]}@example.com",
        "caller",
        "E2E Caller A",
    )


@pytest.fixture
def e2e_caller_b(db_session: Session) -> Tuple[User, str]:
    return create_e2e_user(
        db_session,
        f"{E2E_CALLER_PREFIX}caller_b_{uuid.uuid4().hex[:6]}@example.com",
        "caller",
        "E2E Caller B",
    )


@pytest.fixture
def e2e_admin(db_session: Session) -> Tuple[User, str]:
    return create_e2e_user(
        db_session,
        f"{E2E_ADMIN_PREFIX}admin_{uuid.uuid4().hex[:6]}@example.com",
        "admin",
        "E2E Admin User",
    )


# ===========================================================================
# 1. Authentication & JWT Validation Tests (401)
# ===========================================================================


def test_missing_jwt_returns_401(client: TestClient) -> None:
    """Accessing protected endpoints without Authorization header returns 401."""
    resp_me = client.get("/api/v1/auth/me")
    assert resp_me.status_code == 401

    resp_apps = client.get("/api/v1/applications/")
    assert resp_apps.status_code == 401

    resp_caller = client.get("/api/v1/caller/leads")
    assert resp_caller.status_code == 401

    resp_admin = client.get("/api/v1/admin/dashboard/metrics")
    assert resp_admin.status_code == 401


def test_invalid_jwt_returns_401(client: TestClient) -> None:
    """Accessing protected endpoints with an invalid or malformed token returns 401."""
    bad_headers = {"Authorization": "Bearer invalid.jwt.token"}

    resp = client.get("/api/v1/auth/me", headers=bad_headers)
    assert resp.status_code == 401

    resp_apps = client.get("/api/v1/applications/", headers=bad_headers)
    assert resp_apps.status_code == 401

    resp_caller = client.get("/api/v1/caller/leads", headers=bad_headers)
    assert resp_caller.status_code == 401

    resp_admin = client.get("/api/v1/admin/dashboard/metrics", headers=bad_headers)
    assert resp_admin.status_code == 401


# ===========================================================================
# 2. Customer Scoping & Isolation Tests
# ===========================================================================


def test_customer_can_access_own_resources_only(
    client: TestClient,
    e2e_customer_a: Tuple[User, str],
    e2e_customer_b: Tuple[User, str],
) -> None:
    """Customer can view and manipulate own applications, but receives 404 for another customer's application."""
    user_a, token_a = e2e_customer_a
    user_b, token_b = e2e_customer_b
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Customer A creates an application
    create_resp = client.post(
        "/api/v1/applications/",
        json={"requested_amount": "40000.00", "monthly_income": "50000.00", "age": 28, "work_type": "salaried"},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    app_a_id = create_resp.json()["id"]

    # Customer A can view own application
    view_a_resp = client.get(f"/api/v1/applications/{app_a_id}", headers=headers_a)
    assert view_a_resp.status_code == 200
    assert view_a_resp.json()["id"] == app_a_id

    # Customer B CANNOT view Customer A's application -> 404
    view_b_resp = client.get(f"/api/v1/applications/{app_a_id}", headers=headers_b)
    assert view_b_resp.status_code == 404

    # Customer B CANNOT view Customer A's offers -> 404
    offers_b_resp = client.get(f"/api/v1/applications/{app_a_id}/offers", headers=headers_b)
    assert offers_b_resp.status_code == 404

    # Customer B CANNOT access Customer A's submission status -> 404
    sub_b_resp = client.get(f"/api/v1/applications/{app_a_id}/submission", headers=headers_b)
    assert sub_b_resp.status_code == 404

    # Customer B CANNOT access Customer A's submission events -> 404
    events_b_resp = client.get(f"/api/v1/applications/{app_a_id}/submission/events", headers=headers_b)
    assert events_b_resp.status_code == 404


def test_customer_cannot_access_caller_or_admin_endpoints(
    client: TestClient,
    e2e_customer_a: Tuple[User, str],
) -> None:
    """Customer role receives 403 Forbidden when attempting caller or admin endpoints."""
    _, token_a = e2e_customer_a
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Caller leads route -> 403
    resp_caller = client.get("/api/v1/caller/leads", headers=headers_a)
    assert resp_caller.status_code == 403

    # Admin metrics route -> 403
    resp_metrics = client.get("/api/v1/admin/dashboard/metrics", headers=headers_a)
    assert resp_metrics.status_code == 403


# ===========================================================================
# 3. Caller Scoping & Isolation Tests
# ===========================================================================


def test_caller_strictly_assigned_leads_only(
    client: TestClient,
    db_session: Session,
    e2e_caller_a: Tuple[User, str],
    e2e_caller_b: Tuple[User, str],
) -> None:
    """Caller can only view leads assigned to them and cannot view another caller's leads."""
    caller_a, token_a = e2e_caller_a
    caller_b, token_b = e2e_caller_b
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Create distinct leads assigned to Caller A and Caller B
    ref_a = f"{E2E_LEAD_REF_PREFIX}A_{uuid.uuid4().hex[:6]}"
    ref_b = f"{E2E_LEAD_REF_PREFIX}B_{uuid.uuid4().hex[:6]}"

    create_e2e_lead_with_assignment(db_session, ref_a, "Lead Alpha", caller_a.id)
    create_e2e_lead_with_assignment(db_session, ref_b, "Lead Beta", caller_b.id)

    # Caller A gets their lead list
    resp_a = client.get("/api/v1/caller/leads", headers=headers_a)
    assert resp_a.status_code == 200
    leads_a = resp_a.json()
    refs_for_a = [lead["synthetic_reference"] for lead in leads_a]
    assert ref_a in refs_for_a
    assert ref_b not in refs_for_a, "Caller A must not see Caller B's assigned lead"

    # Caller B gets their lead list
    resp_b = client.get("/api/v1/caller/leads", headers=headers_b)
    assert resp_b.status_code == 200
    leads_b = resp_b.json()
    refs_for_b = [lead["synthetic_reference"] for lead in leads_b]
    assert ref_b in refs_for_b
    assert ref_a not in refs_for_b, "Caller B must not see Caller A's assigned lead"


def test_caller_cannot_access_customer_or_admin_endpoints(
    client: TestClient,
    e2e_caller_a: Tuple[User, str],
) -> None:
    """Caller role receives 403 Forbidden when attempting customer application or admin endpoints."""
    _, token_a = e2e_caller_a
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Customer endpoints -> 403
    resp_app_list = client.get("/api/v1/applications/", headers=headers_a)
    assert resp_app_list.status_code == 403

    resp_app_create = client.post(
        "/api/v1/applications/",
        json={"requested_amount": "50000.00", "monthly_income": "60000.00", "age": 30, "work_type": "salaried"},
        headers=headers_a,
    )
    assert resp_app_create.status_code == 403

    # Admin endpoints -> 403
    resp_admin = client.get("/api/v1/admin/dashboard/metrics", headers=headers_a)
    assert resp_admin.status_code == 403


# ===========================================================================
# 4. Admin Scoping & Zero-PII Telemetry Tests
# ===========================================================================


def test_admin_metrics_contains_no_customer_pii(
    client: TestClient,
    e2e_admin: Tuple[User, str],
) -> None:
    """Admin dashboard endpoints return aggregate telemetry without customer PII."""
    _, admin_token = e2e_admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    resp_metrics = client.get("/api/v1/admin/dashboard/metrics", headers=admin_headers)
    assert resp_metrics.status_code == 200
    metrics_data = resp_metrics.json()

    # Check aggregate fields exist
    assert "total_applications" in metrics_data
    assert "total_submissions" in metrics_data
    assert "applications_by_status" in metrics_data

    # Check zero customer PII: no names, no email addresses, no personal records
    raw_text = resp_metrics.text
    assert "@example.com" not in raw_text
    assert "customer_name" not in raw_text
    assert "password_hash" not in raw_text


def test_admin_cannot_access_customer_or_caller_endpoints(
    client: TestClient,
    e2e_admin: Tuple[User, str],
) -> None:
    """Admin role receives 403 Forbidden when attempting customer or caller workflows."""
    _, admin_token = e2e_admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Customer endpoints -> 403
    resp_app_list = client.get("/api/v1/applications/", headers=admin_headers)
    assert resp_app_list.status_code == 403

    # Caller leads -> 403
    resp_caller = client.get("/api/v1/caller/leads", headers=admin_headers)
    assert resp_caller.status_code == 403
