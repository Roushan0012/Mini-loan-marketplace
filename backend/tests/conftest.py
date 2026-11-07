import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Ensure tests run against the isolated test database and isolated test secret
os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "mini_loan_marketplace_test")
os.environ["JWT_SECRET_KEY"] = os.getenv(
    "TEST_JWT_SECRET_KEY", "test-isolated-dummy-secret-key-for-auth-testing-12345678"
)

from app.core.config import get_settings

get_settings.cache_clear()

from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

TEST_EMAIL_PREFIX = "pytest_auth_"


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient connected to the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator:
    """Provide a database session to the isolated test database."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def cleanup_test_auth_records() -> Generator[None, None, None]:
    """Clean up only records created by auth tests without truncating tables."""
    yield
    with SessionLocal() as session:
        session.query(User).filter(User.email.startswith(TEST_EMAIL_PREFIX)).delete(
            synchronize_session=False
        )
        session.commit()
