from decimal import Decimal
from typing import Tuple

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.loan_application import LoanApplication
from app.models.user import User


# ==============================================================================
# Authentication and Role Checks (1–3)
# ==============================================================================


def test_missing_token_cannot_create_application(client: TestClient):
    """1. Missing token cannot create an application and returns HTTP 401."""
    payload = {
        "age": 28,
        "monthly_income": "60000.00",
        "work_type": "salaried",
        "requested_amount": "250000.00",
    }
    response = client.post("/api/v1/applications", json=payload)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_caller_cannot_create_application(
    client: TestClient,
    rbac_caller_a: Tuple[User, str],
):
    """2. Caller role cannot create an application and returns HTTP 403."""
    _, caller_token = rbac_caller_a
    payload = {
        "age": 30,
        "monthly_income": "50000.00",
        "work_type": "salaried",
        "requested_amount": "100000.00",
    }
    response = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Authorization": f"Bearer {caller_token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_admin_cannot_create_application(
    client: TestClient,
    rbac_admin: Tuple[User, str],
):
    """3. Admin role cannot create an application and returns HTTP 403."""
    _, admin_token = rbac_admin
    payload = {
        "age": 35,
        "monthly_income": "80000.00",
        "work_type": "self_employed",
        "requested_amount": "500000.00",
    }
    response = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


# ==============================================================================
# Application Creation Tests (4–13)
# ==============================================================================


def test_valid_customer_can_create_application(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """4. Valid customer can create an application and receive HTTP 201."""
    _, customer_token = app_customer_a
    payload = {
        "age": 29,
        "monthly_income": "55000.00",
        "work_type": "salaried",
        "requested_amount": "200000.00",
    }
    response = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 201

    data = response.json()
    assert data["age"] == 29
    assert Decimal(str(data["monthly_income"])) == Decimal("55000.00")
    assert data["work_type"] == "salaried"
    assert Decimal(str(data["requested_amount"])) == Decimal("200000.00")
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_new_application_status_is_always_draft(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """5. New application status is always initialized to 'draft'."""
    _, customer_token = app_customer_a
    payload = {
        "age": 32,
        "monthly_income": "75000.00",
        "work_type": "self_employed",
        "requested_amount": "300000.00",
    }
    response = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_customer_id_is_assigned_from_authenticated_user(
    client: TestClient,
    db_session: Session,
    app_customer_a: Tuple[User, str],
):
    """6. customer_id is assigned from the authenticated user and stored in DB."""
    customer_user, customer_token = app_customer_a
    payload = {
        "age": 26,
        "monthly_income": "45000.00",
        "work_type": "salaried",
        "requested_amount": "150000.00",
    }
    response = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 201
    app_id = response.json()["id"]

    db_app = db_session.get(LoanApplication, app_id)
    assert db_app is not None
    assert db_app.customer_id == customer_user.id
    assert db_app.lead_id is None


def test_request_containing_customer_id_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """7. Request containing customer_id is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    payload = {
        "age": 30,
        "monthly_income": "50000.00",
        "work_type": "salaried",
        "requested_amount": "100000.00",
        "customer_id": 99999,
    }
    response = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 422


def test_request_containing_status_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """8. Request containing status is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    payload = {
        "age": 30,
        "monthly_income": "50000.00",
        "work_type": "salaried",
        "requested_amount": "100000.00",
        "status": "approved",
    }
    response = client.post(
        "/api/v1/applications",
        json=payload,
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 422


def test_invalid_age_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """9. Non-positive age (zero or negative) is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    for invalid_age in [0, -5]:
        response = client.post(
            "/api/v1/applications",
            json={
                "age": invalid_age,
                "monthly_income": "50000.00",
                "work_type": "salaried",
                "requested_amount": "100000.00",
            },
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 422


def test_negative_monthly_income_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """10. Negative monthly income is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    response = client.post(
        "/api/v1/applications",
        json={
            "age": 30,
            "monthly_income": "-1000.00",
            "work_type": "salaried",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 422


def test_zero_or_negative_requested_amount_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """11. Zero or negative requested amount is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    for invalid_amt in ["0.00", "-50000.00"]:
        response = client.post(
            "/api/v1/applications",
            json={
                "age": 30,
                "monthly_income": "50000.00",
                "work_type": "salaried",
                "requested_amount": invalid_amt,
            },
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 422


def test_unsupported_work_type_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """12. Unsupported work_type is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    response = client.post(
        "/api/v1/applications",
        json={
            "age": 30,
            "monthly_income": "50000.00",
            "work_type": "unemployed_gig",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 422


def test_invalid_monetary_precision_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """13. Invalid monetary precision (>2 decimal places) is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    response = client.post(
        "/api/v1/applications",
        json={
            "age": 30,
            "monthly_income": "50000.00",
            "work_type": "salaried",
            "requested_amount": "100000.555",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 422


# ==============================================================================
# Listing and Reading Tests (14–18)
# ==============================================================================


def test_customer_can_list_own_applications(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """14. Customer can list their own loan applications."""
    _, customer_token = app_customer_a
    client.post(
        "/api/v1/applications",
        json={
            "age": 28,
            "monthly_income": "50000.00",
            "work_type": "salaried",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    client.post(
        "/api/v1/applications",
        json={
            "age": 29,
            "monthly_income": "60000.00",
            "work_type": "other",
            "requested_amount": "150000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    response = client.get(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 200
    apps = response.json()
    assert len(apps) == 2


def test_customer_cannot_see_other_customer_applications(
    client: TestClient,
    app_customer_a: Tuple[User, str],
    app_customer_b: Tuple[User, str],
):
    """15. Customer cannot see another customer's loan applications."""
    _, token_a = app_customer_a
    _, token_b = app_customer_b

    resp_a = client.post(
        "/api/v1/applications",
        json={
            "age": 31,
            "monthly_income": "70000.00",
            "work_type": "salaried",
            "requested_amount": "200000.00",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    app_a_id = resp_a.json()["id"]

    resp_b = client.post(
        "/api/v1/applications",
        json={
            "age": 40,
            "monthly_income": "90000.00",
            "work_type": "self_employed",
            "requested_amount": "400000.00",
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )
    app_b_id = resp_b.json()["id"]

    # Customer A should see only app A
    list_a = client.get("/api/v1/applications", headers={"Authorization": f"Bearer {token_a}"})
    ids_a = [item["id"] for item in list_a.json()]
    assert app_a_id in ids_a
    assert app_b_id not in ids_a

    # Customer B should see only app B
    list_b = client.get("/api/v1/applications", headers={"Authorization": f"Bearer {token_b}"})
    ids_b = [item["id"] for item in list_b.json()]
    assert app_b_id in ids_b
    assert app_a_id not in ids_b


def test_customer_can_retrieve_own_application(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """16. Customer can retrieve their own application by ID."""
    _, customer_token = app_customer_a
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 33,
            "monthly_income": "62000.00",
            "work_type": "salaried",
            "requested_amount": "220000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    app_id = create_resp.json()["id"]

    get_resp = client.get(
        f"/api/v1/applications/{app_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == app_id
    assert get_resp.json()["age"] == 33


def test_customer_gets_404_for_other_customer_application(
    client: TestClient,
    app_customer_a: Tuple[User, str],
    app_customer_b: Tuple[User, str],
):
    """17. Customer gets HTTP 404 when attempting to access another customer's application."""
    _, token_a = app_customer_a
    _, token_b = app_customer_b

    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 35,
            "monthly_income": "85000.00",
            "work_type": "self_employed",
            "requested_amount": "350000.00",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    app_a_id = create_resp.json()["id"]

    # Customer B attempts to access Customer A's application
    get_resp = client.get(
        f"/api/v1/applications/{app_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Loan application not found."


def test_customer_gets_404_for_unknown_application_id(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """18. Customer gets HTTP 404 for an unknown application ID."""
    _, customer_token = app_customer_a
    response = client.get(
        "/api/v1/applications/99999999",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Loan application not found."


# ==============================================================================
# Updating Tests (19–25)
# ==============================================================================


def test_customer_can_update_own_draft(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """19. Customer can update their own draft loan application."""
    _, customer_token = app_customer_a
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 27,
            "monthly_income": "48000.00",
            "work_type": "salaried",
            "requested_amount": "180000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    app_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"requested_amount": "250000.00"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert patch_resp.status_code == 200
    assert Decimal(str(patch_resp.json()["requested_amount"])) == Decimal("250000.00")
    assert patch_resp.json()["age"] == 27


def test_partial_update_changes_only_supplied_fields(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """20. Partial update changes only supplied fields and preserves others."""
    _, customer_token = app_customer_a
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 34,
            "monthly_income": "65000.00",
            "work_type": "salaried",
            "requested_amount": "300000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    app_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"age": 35, "work_type": "self_employed"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["age"] == 35
    assert data["work_type"] == "self_employed"
    assert Decimal(str(data["monthly_income"])) == Decimal("65000.00")
    assert Decimal(str(data["requested_amount"])) == Decimal("300000.00")


def test_customer_cannot_update_other_customer_application(
    client: TestClient,
    app_customer_a: Tuple[User, str],
    app_customer_b: Tuple[User, str],
):
    """21. Customer cannot update another customer's application and receives HTTP 404."""
    _, token_a = app_customer_a
    _, token_b = app_customer_b

    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 30,
            "monthly_income": "50000.00",
            "work_type": "salaried",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    app_a_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/applications/{app_a_id}",
        json={"requested_amount": "999999.00"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert patch_resp.status_code == 404
    assert patch_resp.json()["detail"] == "Loan application not found."


def test_customer_cannot_update_status_through_request(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """22. Customer cannot update status through PATCH request and receives HTTP 422."""
    _, customer_token = app_customer_a
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 28,
            "monthly_income": "50000.00",
            "work_type": "salaried",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    app_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert patch_resp.status_code == 422


def test_empty_update_request_is_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """23. Empty update request is rejected with HTTP 422."""
    _, customer_token = app_customer_a
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 28,
            "monthly_income": "50000.00",
            "work_type": "salaried",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    app_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/applications/{app_id}",
        json={},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert patch_resp.status_code == 422


def test_explicit_null_update_values_are_rejected(
    client: TestClient,
    app_customer_a: Tuple[User, str],
):
    """24. Explicit null update values are rejected with HTTP 422."""
    _, customer_token = app_customer_a
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 28,
            "monthly_income": "50000.00",
            "work_type": "salaried",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    app_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"requested_amount": None},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert patch_resp.status_code == 422


def test_updating_non_draft_application_returns_409(
    client: TestClient,
    db_session: Session,
    app_customer_a: Tuple[User, str],
):
    """25. Updating a non-draft application returns HTTP 409 Conflict."""
    _, customer_token = app_customer_a
    create_resp = client.post(
        "/api/v1/applications",
        json={
            "age": 28,
            "monthly_income": "50000.00",
            "work_type": "salaried",
            "requested_amount": "100000.00",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    app_id = create_resp.json()["id"]

    # Transition status to 'submitted' directly in database
    db_app = db_session.get(LoanApplication, app_id)
    assert db_app is not None
    db_app.status = "submitted"
    db_session.commit()

    patch_resp = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"requested_amount": "150000.00"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert patch_resp.status_code == 409
    assert "cannot be modified" in patch_resp.json()["detail"].lower()
