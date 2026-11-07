from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from tests.conftest import TEST_EMAIL_PREFIX


# ==============================================================================
# Registration Tests (1–6)
# ==============================================================================


def test_successful_customer_registration_returns_201(client: TestClient):
    """1. Successful customer registration returns HTTP 201."""
    email = f"{TEST_EMAIL_PREFIX}reg_success@example.com"
    payload = {
        "full_name": "Test Customer One",
        "email": email,
        "password": "SecurePassword123!",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["email"] == email
    assert data["full_name"] == "Test Customer One"
    assert data["is_active"] is True
    assert "id" in data


def test_registered_user_has_role_customer(client: TestClient, db_session: Session):
    """2. The registered user has role customer in both response and database."""
    email = f"{TEST_EMAIL_PREFIX}reg_role@example.com"
    payload = {
        "full_name": "Customer Role Check",
        "email": email,
        "password": "SecurePassword123!",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["role"] == "customer"

    db_user = db_session.query(User).filter(User.email == email).first()
    assert db_user is not None
    assert db_user.role == "customer"


def test_password_stored_only_as_argon2_hash(client: TestClient, db_session: Session):
    """3. Password is stored only as an Argon2 hash, never in plaintext."""
    raw_password = "PlaintextSecretPassword123!"
    email = f"{TEST_EMAIL_PREFIX}reg_hash@example.com"
    payload = {
        "full_name": "Hash Verification User",
        "email": email,
        "password": raw_password,
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    db_user = db_session.query(User).filter(User.email == email).first()
    assert db_user is not None
    assert db_user.password_hash != raw_password
    assert db_user.password_hash.startswith("$argon2id$")
    assert verify_password(raw_password, db_user.password_hash) is True


def test_duplicate_email_returns_409(client: TestClient):
    """4. Duplicate email returns HTTP 409 conflict, including case-insensitive checks."""
    email = f"{TEST_EMAIL_PREFIX}duplicate@example.com"
    payload = {
        "full_name": "First User",
        "email": email,
        "password": "SecurePassword123!",
    }

    first_resp = client.post("/api/v1/auth/register", json=payload)
    assert first_resp.status_code == 201

    # Attempt registration with identical email in uppercase
    dup_payload = {
        "full_name": "Second User",
        "email": email.upper(),
        "password": "AnotherPassword456!",
    }
    dup_resp = client.post("/api/v1/auth/register", json=dup_payload)
    assert dup_resp.status_code == 409
    assert "already exists" in dup_resp.json()["detail"].lower()


def test_registration_with_role_field_is_rejected(client: TestClient):
    """5. Registration with role='admin' or any unexpected field is rejected."""
    email = f"{TEST_EMAIL_PREFIX}forbidden_role@example.com"
    payload = {
        "full_name": "Attacker Trying Admin",
        "email": email,
        "password": "SecurePassword123!",
        "role": "admin",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_registration_response_does_not_contain_password_or_hash(client: TestClient):
    """6. Registration response does not contain password_hash or password."""
    email = f"{TEST_EMAIL_PREFIX}no_leak@example.com"
    payload = {
        "full_name": "No Leak Customer",
        "email": email,
        "password": "SecurePassword123!",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "password" not in data
    assert "password_hash" not in data


# ==============================================================================
# Login Tests (7–11)
# ==============================================================================


def test_correct_credentials_return_access_token(client: TestClient):
    """7. Correct credentials return an access token."""
    email = f"{TEST_EMAIL_PREFIX}login_success@example.com"
    password = "CorrectLoginPass123!"

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Login User", "email": email, "password": password},
    )
    assert reg_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200

    data = login_resp.json()
    assert "access_token" in data
    assert len(data["access_token"]) > 20


def test_token_type_is_bearer(client: TestClient):
    """8. Token type is bearer and expires_in is populated."""
    email = f"{TEST_EMAIL_PREFIX}bearer_type@example.com"
    password = "CorrectBearerPass123!"

    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Bearer User", "email": email, "password": password},
    )

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200

    data = login_resp.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_incorrect_password_returns_401(client: TestClient):
    """9. Incorrect password returns HTTP 401 with WWW-Authenticate header."""
    email = f"{TEST_EMAIL_PREFIX}bad_pw@example.com"
    password = "CorrectPassword123!"

    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Bad Pw User", "email": email, "password": password},
    )

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword456!"},
    )
    assert login_resp.status_code == 401
    assert login_resp.headers.get("www-authenticate") == "Bearer"
    assert login_resp.json()["detail"] == "Invalid email or password."


def test_unknown_email_returns_same_generic_401(client: TestClient):
    """10. Unknown email returns the same generic HTTP 401 response without leaking email status."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": f"{TEST_EMAIL_PREFIX}unknown_user@example.com", "password": "SomePassword123!"},
    )
    assert login_resp.status_code == 401
    assert login_resp.headers.get("www-authenticate") == "Bearer"
    assert login_resp.json()["detail"] == "Invalid email or password."


def test_inactive_user_cannot_log_in(client: TestClient, db_session: Session):
    """11. Inactive user cannot log in and receives generic 401."""
    email = f"{TEST_EMAIL_PREFIX}inactive_login@example.com"
    password = "InactivePassword123!"

    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Inactive User", "email": email, "password": password},
    )

    # Deactivate the user directly in database
    db_user = db_session.query(User).filter(User.email == email).first()
    assert db_user is not None
    db_user.is_active = False
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 401
    assert login_resp.headers.get("www-authenticate") == "Bearer"
    assert login_resp.json()["detail"] == "Invalid email or password."


# ==============================================================================
# Current User Tests (12–17)
# ==============================================================================


def test_missing_bearer_token_returns_401(client: TestClient):
    """12. Missing bearer token returns HTTP 401 with WWW-Authenticate header."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_valid_token_returns_correct_public_user_profile(client: TestClient):
    """13. Valid token returns the correct public user profile and never leaks password_hash."""
    email = f"{TEST_EMAIL_PREFIX}me_profile@example.com"
    password = "ProfilePassword123!"

    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Profile Customer", "email": email, "password": password},
    )

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_resp.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == email
    assert data["full_name"] == "Profile Customer"
    assert data["role"] == "customer"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data


def test_expired_token_returns_401(client: TestClient, db_session: Session):
    """14. Expired token returns HTTP 401."""
    email = f"{TEST_EMAIL_PREFIX}expired@example.com"
    password = "ExpiredPassword123!"

    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Expired User", "email": email, "password": password},
    )
    db_user = db_session.query(User).filter(User.email == email).first()
    assert db_user is not None

    expired_token = create_access_token(
        user_id=db_user.id,
        expires_delta=timedelta(seconds=-10),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_tampered_token_returns_401(client: TestClient):
    """15. Tampered token returns HTTP 401."""
    email = f"{TEST_EMAIL_PREFIX}tampered@example.com"
    password = "TamperedPassword123!"

    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Tamper User", "email": email, "password": password},
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_resp.json()["access_token"]
    tampered_token = token[:-4] + "abcd"

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_token_with_invalid_subject_returns_401(client: TestClient):
    """16. Token with an invalid non-numeric or negative subject returns HTTP 401."""
    now = datetime.now(timezone.utc)
    invalid_payload = {
        "sub": "not-an-integer-id",
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }
    invalid_token = jwt.encode(
        invalid_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {invalid_token}"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_deleted_or_nonexistent_user_token_returns_401(client: TestClient):
    """17. Deleted or nonexistent user token returns HTTP 401."""
    token = create_access_token(user_id=99999999)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
