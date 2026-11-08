from typing import Optional
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine repository root directory where .env is located
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

INSECURE_JWT_PLACEHOLDERS = {
    "",
    "secret",
    "jwt-secret",
    "change-me",
    "changethis",
    "placeholder",
    "your-secret-key",
    "your-secret-key-here",
    "change-this-to-a-secure-random-secret-key-in-production",
    "change-this-to-a-secure-jwt-secret-key-in-local-env",
}

INSECURE_WEBHOOK_PLACEHOLDERS = {
    "",
    "secret",
    "webhook-secret",
    "change-me",
    "changethis",
    "placeholder",
    "your-secret-key",
    "your-secret-key-here",
    "change-this-to-a-secure-webhook-secret-key-in-local-env",
}


class Settings(BaseSettings):
    """Application, security, and PostgreSQL configuration settings."""

    # Project settings
    PROJECT_NAME: str = "Mini Loan Marketplace"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Security & JWT configuration
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS Origins (comma-separated string of permitted origins)
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    )

    # Mock Lender Webhook Configuration
    MOCK_LENDER_WEBHOOK_SECRET: Optional[str] = None

    # PostgreSQL configuration
    POSTGRES_DB: str = "mini_loan_marketplace"
    POSTGRES_USER: str = "marketplace_user"
    POSTGRES_PASSWORD: str = "local_dev_password_change_me"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        trimmed = (v or "").strip()
        if not trimmed:
            raise ValueError(
                "JWT_SECRET_KEY must be configured in environment or .env file and cannot be empty."
            )
        if trimmed.lower() in INSECURE_JWT_PLACEHOLDERS or len(trimmed) < 32:
            raise ValueError(
                "JWT_SECRET_KEY cannot use insecure placeholders and must be at least 32 characters long."
            )
        return trimmed

    @field_validator("MOCK_LENDER_WEBHOOK_SECRET")
    @classmethod
    def validate_webhook_secret(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        if trimmed.lower() in INSECURE_WEBHOOK_PLACEHOLDERS or len(trimmed) < 32:
            raise ValueError(
                "MOCK_LENDER_WEBHOOK_SECRET cannot use insecure placeholders and must be at least 32 characters long."
            )
        return trimmed

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS into a clean list of allowed origins."""
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()


settings = get_settings()
