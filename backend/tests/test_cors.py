from fastapi.testclient import TestClient

from app.main import app


def test_allowed_vite_origin_receives_cors_headers() -> None:
    """Allowed Vite origin (http://localhost:5173) receives Access-Control-Allow-Origin header."""
    client = TestClient(app)
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_disallowed_origin_does_not_receive_cors_header() -> None:
    """Disallowed origin does not receive Access-Control-Allow-Origin header."""
    client = TestClient(app)
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://malicious-external-site.com"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allows_authorization_and_idempotency_headers() -> None:
    """OPTIONS preflight from allowed origin approves Authorization and Idempotency-Key headers."""
    client = TestClient(app)
    response = client.options(
        "/api/v1/applications",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type, idempotency-key",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers
    assert "idempotency-key" in allowed_headers


def test_cors_allow_credentials_is_false() -> None:
    """Ensure allow_credentials is not set to true since Bearer authentication is used."""
    client = TestClient(app)
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    # access-control-allow-credentials should not be "true"
    assert response.headers.get("access-control-allow-credentials") != "true"
