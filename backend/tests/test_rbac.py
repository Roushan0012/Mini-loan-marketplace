from decimal import Decimal
from typing import Tuple

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.permissions import require_admin, require_caller, require_customer
from app.models.lead import Lead
from app.models.loan_application import LoanApplication
from app.models.user import User
from tests.conftest import (
    TEST_RBAC_REF_PREFIX,
    create_fictional_lead_with_assignment,
)


# ==============================================================================
# A. Authentication and Authorization Tests (1–7)
# ==============================================================================


def test_missing_token_caller_leads_returns_401(client: TestClient):
    """1. Missing token accessing caller leads returns 401 with WWW-Authenticate header."""
    response = client.get("/api/v1/caller/leads")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_missing_token_admin_metrics_returns_401(client: TestClient):
    """2. Missing token accessing admin metrics returns 401 with WWW-Authenticate header."""
    response = client.get("/api/v1/admin/dashboard/metrics")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_invalid_token_protected_routes_returns_401(client: TestClient):
    """3. Invalid or corrupted token accessing protected routes returns 401."""
    bad_headers = {"Authorization": "Bearer invalid.token.payload"}

    caller_resp = client.get("/api/v1/caller/leads", headers=bad_headers)
    assert caller_resp.status_code == 401
    assert caller_resp.headers.get("www-authenticate") == "Bearer"

    admin_resp = client.get("/api/v1/admin/dashboard/metrics", headers=bad_headers)
    assert admin_resp.status_code == 401
    assert admin_resp.headers.get("www-authenticate") == "Bearer"


def test_customer_accessing_caller_leads_returns_403(
    client: TestClient,
    rbac_customer: Tuple[User, str],
):
    """4. Customer role accessing caller leads returns HTTP 403 Forbidden."""
    _, customer_token = rbac_customer
    response = client.get(
        "/api/v1/caller/leads",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_customer_accessing_admin_metrics_returns_403(
    client: TestClient,
    rbac_customer: Tuple[User, str],
):
    """5. Customer role accessing admin metrics returns HTTP 403 Forbidden."""
    _, customer_token = rbac_customer
    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_caller_accessing_admin_metrics_returns_403(
    client: TestClient,
    rbac_caller_a: Tuple[User, str],
):
    """6. Caller role accessing admin metrics returns HTTP 403 Forbidden."""
    _, caller_token = rbac_caller_a
    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_admin_accessing_caller_leads_returns_403(
    client: TestClient,
    rbac_admin: Tuple[User, str],
):
    """7. Admin role accessing caller leads returns HTTP 403 Forbidden."""
    _, admin_token = rbac_admin
    response = client.get(
        "/api/v1/caller/leads",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


# ==============================================================================
# B. Caller Isolation Tests (8–12)
# ==============================================================================


def test_caller_a_can_access_own_assigned_leads(
    client: TestClient,
    db_session: Session,
    rbac_caller_a: Tuple[User, str],
):
    """8. Caller A can access their own assigned mock leads."""
    caller_a_user, caller_a_token = rbac_caller_a

    lead1 = create_fictional_lead_with_assignment(
        db_session,
        ref=f"{TEST_RBAC_REF_PREFIX}lead_a1",
        applicant_name="Applicant Alpha",
        caller_id=caller_a_user.id,
        amount=Decimal("15000.00"),
    )
    lead2 = create_fictional_lead_with_assignment(
        db_session,
        ref=f"{TEST_RBAC_REF_PREFIX}lead_a2",
        applicant_name="Applicant Beta",
        caller_id=caller_a_user.id,
        amount=Decimal("25000.00"),
    )

    response = client.get(
        "/api/v1/caller/leads",
        headers={"Authorization": f"Bearer {caller_a_token}"},
    )
    assert response.status_code == 200

    leads = response.json()
    assert len(leads) == 2
    returned_refs = {item["synthetic_reference"] for item in leads}
    assert lead1.synthetic_reference in returned_refs
    assert lead2.synthetic_reference in returned_refs

    # Verify response schema fields
    first = leads[0]
    assert "synthetic_reference" in first
    assert "applicant_name" in first
    assert "age" in first
    assert "monthly_income" in first
    assert "work_type" in first
    assert "requested_amount" in first
    assert "status" in first
    assert "assigned_at" in first


def test_caller_a_cannot_see_caller_b_assigned_leads(
    client: TestClient,
    db_session: Session,
    rbac_caller_a: Tuple[User, str],
    rbac_caller_b: Tuple[User, str],
):
    """9. Caller A cannot see Caller B's assigned mock leads."""
    caller_a_user, caller_a_token = rbac_caller_a
    caller_b_user, caller_b_token = rbac_caller_b

    lead_a = create_fictional_lead_with_assignment(
        db_session,
        ref=f"{TEST_RBAC_REF_PREFIX}lead_for_a",
        applicant_name="Applicant For A",
        caller_id=caller_a_user.id,
    )
    lead_b = create_fictional_lead_with_assignment(
        db_session,
        ref=f"{TEST_RBAC_REF_PREFIX}lead_for_b",
        applicant_name="Applicant For B",
        caller_id=caller_b_user.id,
    )

    # Caller A should see only lead_a
    resp_a = client.get(
        "/api/v1/caller/leads",
        headers={"Authorization": f"Bearer {caller_a_token}"},
    )
    assert resp_a.status_code == 200
    refs_a = [item["synthetic_reference"] for item in resp_a.json()]
    assert lead_a.synthetic_reference in refs_a
    assert lead_b.synthetic_reference not in refs_a

    # Caller B should see only lead_b
    resp_b = client.get(
        "/api/v1/caller/leads",
        headers={"Authorization": f"Bearer {caller_b_token}"},
    )
    assert resp_b.status_code == 200
    refs_b = [item["synthetic_reference"] for item in resp_b.json()]
    assert lead_b.synthetic_reference in refs_b
    assert lead_a.synthetic_reference not in refs_b


def test_caller_cannot_override_caller_identity(
    client: TestClient,
    db_session: Session,
    rbac_caller_a: Tuple[User, str],
    rbac_caller_b: Tuple[User, str],
):
    """10. Caller A cannot request or override another caller's identity via query params."""
    caller_a_user, caller_a_token = rbac_caller_a
    caller_b_user, _ = rbac_caller_b

    create_fictional_lead_with_assignment(
        db_session,
        ref=f"{TEST_RBAC_REF_PREFIX}override_test_lead",
        applicant_name="Applicant B Sensitive",
        caller_id=caller_b_user.id,
    )

    # Caller A tries to pass caller_id=caller_b_user.id in query parameters
    response = client.get(
        f"/api/v1/caller/leads?caller_id={caller_b_user.id}",
        headers={"Authorization": f"Bearer {caller_a_token}"},
    )
    assert response.status_code == 200
    # Must still only return Caller A's assigned leads (which is empty)
    assert len(response.json()) == 0


def test_caller_with_no_assigned_leads_receives_empty_list(
    client: TestClient,
    rbac_unassigned_caller: Tuple[User, str],
):
    """11. Caller with no assigned leads receives an empty list."""
    _, unassigned_token = rbac_unassigned_caller
    response = client.get(
        "/api/v1/caller/leads",
        headers={"Authorization": f"Bearer {unassigned_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_caller_leads_pagination(
    client: TestClient,
    db_session: Session,
    rbac_caller_a: Tuple[User, str],
):
    """12. Pagination limit and offset work correctly with stable ID ordering."""
    caller_a_user, caller_a_token = rbac_caller_a

    leads = []
    for i in range(5):
        l = create_fictional_lead_with_assignment(
            db_session,
            ref=f"{TEST_RBAC_REF_PREFIX}page_lead_{i}",
            applicant_name=f"Applicant Number {i}",
            caller_id=caller_a_user.id,
            amount=Decimal(f"{(i+1)*10000}.00"),
        )
        leads.append(l)

    # First page: limit=2, offset=0
    resp_page1 = client.get(
        "/api/v1/caller/leads?limit=2&offset=0",
        headers={"Authorization": f"Bearer {caller_a_token}"},
    )
    assert resp_page1.status_code == 200
    page1_items = resp_page1.json()
    assert len(page1_items) == 2
    assert page1_items[0]["id"] == leads[0].id
    assert page1_items[1]["id"] == leads[1].id

    # Second page: limit=2, offset=2
    resp_page2 = client.get(
        "/api/v1/caller/leads?limit=2&offset=2",
        headers={"Authorization": f"Bearer {caller_a_token}"},
    )
    assert resp_page2.status_code == 200
    page2_items = resp_page2.json()
    assert len(page2_items) == 2
    assert page2_items[0]["id"] == leads[2].id
    assert page2_items[1]["id"] == leads[3].id

    # Beyond total: offset=10
    resp_empty = client.get(
        "/api/v1/caller/leads?limit=2&offset=10",
        headers={"Authorization": f"Bearer {caller_a_token}"},
    )
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []


# ==============================================================================
# C. Admin Dashboard Tests (13–18)
# ==============================================================================


def test_admin_can_access_aggregate_metrics(
    client: TestClient,
    rbac_admin: Tuple[User, str],
):
    """13. Admin can access aggregate metrics."""
    _, admin_token = rbac_admin
    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


def test_admin_metrics_contains_all_expected_fields(
    client: TestClient,
    rbac_admin: Tuple[User, str],
):
    """14. Response contains all expected aggregate count fields."""
    _, admin_token = rbac_admin
    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "total_leads" in data
    assert "total_applications" in data
    assert "total_match_runs" in data
    assert "total_offers" in data
    assert "total_submissions" in data
    assert "applications_by_status" in data
    assert "lender_events_by_processing_status" in data


def test_admin_grouped_counts_returned(
    client: TestClient,
    db_session: Session,
    rbac_admin: Tuple[User, str],
    rbac_customer: Tuple[User, str],
):
    """15. Grouped application and event counts are accurately returned."""
    _, admin_token = rbac_admin
    customer_user, _ = rbac_customer

    # Add 2 applications with different statuses
    app1 = LoanApplication(
        customer_id=customer_user.id,
        age=30,
        monthly_income=Decimal("50000.00"),
        work_type="salaried",
        requested_amount=Decimal("100000.00"),
        status="draft",
    )
    app2 = LoanApplication(
        customer_id=customer_user.id,
        age=35,
        monthly_income=Decimal("60000.00"),
        work_type="self_employed",
        requested_amount=Decimal("200000.00"),
        status="submitted",
    )
    db_session.add_all([app1, app2])
    db_session.commit()

    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_applications"] >= 2
    assert "draft" in data["applications_by_status"]
    assert "submitted" in data["applications_by_status"]


def test_no_customer_pii_in_admin_metrics(
    client: TestClient,
    rbac_admin: Tuple[User, str],
):
    """16. No individual customer names, emails, or personal data appear in response."""
    _, admin_token = rbac_admin
    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    text_content = response.text.lower()
    for forbidden in ["customer", "email", "full_name", "applicant_name", "ssn", "pan"]:
        assert f'"{forbidden}"' not in text_content


def test_no_password_hash_or_raw_payloads_in_admin_metrics(
    client: TestClient,
    rbac_admin: Tuple[User, str],
):
    """17. No password_hash or raw event payload appears in admin metrics."""
    _, admin_token = rbac_admin
    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    text_content = response.text.lower()
    assert "password_hash" not in text_content
    assert "event_payload" not in text_content


def test_empty_tables_return_zero_counts_safely(
    client: TestClient,
    rbac_admin: Tuple[User, str],
):
    """18. When tables contain no domain activity, zero counts and empty dicts are returned safely."""
    _, admin_token = rbac_admin
    response = client.get(
        "/api/v1/admin/dashboard/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["total_leads"], int)
    assert isinstance(data["total_applications"], int)
    assert isinstance(data["applications_by_status"], dict)
    assert isinstance(data["lender_events_by_processing_status"], dict)


# ==============================================================================
# D. Generic Role Dependencies (19–22)
# ==============================================================================


def test_require_customer_allows_customer(rbac_customer: Tuple[User, str]):
    """19. require_customer allows a user with role customer."""
    customer_user, _ = rbac_customer
    result = require_customer(current_user=customer_user)
    assert result == customer_user


def test_require_customer_rejects_caller_and_admin(
    rbac_caller_a: Tuple[User, str],
    rbac_admin: Tuple[User, str],
):
    """20. require_customer rejects a caller and admin with HTTP 403."""
    caller_user, _ = rbac_caller_a
    admin_user, _ = rbac_admin

    with pytest.raises(HTTPException) as exc_caller:
        require_customer(current_user=caller_user)
    assert exc_caller.value.status_code == 403

    with pytest.raises(HTTPException) as exc_admin:
        require_customer(current_user=admin_user)
    assert exc_admin.value.status_code == 403


def test_require_caller_allows_caller(
    rbac_caller_a: Tuple[User, str],
    rbac_customer: Tuple[User, str],
):
    """21. require_caller allows a caller and rejects a customer."""
    caller_user, _ = rbac_caller_a
    customer_user, _ = rbac_customer

    result = require_caller(current_user=caller_user)
    assert result == caller_user

    with pytest.raises(HTTPException) as exc:
        require_caller(current_user=customer_user)
    assert exc.value.status_code == 403


def test_require_admin_allows_admin(
    rbac_admin: Tuple[User, str],
    rbac_caller_a: Tuple[User, str],
):
    """22. require_admin allows an admin and rejects a caller."""
    admin_user, _ = rbac_admin
    caller_user, _ = rbac_caller_a

    result = require_admin(current_user=admin_user)
    assert result == admin_user

    with pytest.raises(HTTPException) as exc:
        require_admin(current_user=caller_user)
    assert exc.value.status_code == 403
