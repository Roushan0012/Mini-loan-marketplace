from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_status_code():
    """Verify the health endpoint returns HTTP 200."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_endpoint_response_content():
    """Verify the response contains status = 'ok' and the correct service name."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "mini-loan-marketplace-api"
