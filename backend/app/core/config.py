from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine repository root directory where .env is located
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Application and PostgreSQL configuration settings."""

    # Project settings
    PROJECT_NAME: str = "Mini Loan Marketplace"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL configuration
    POSTGRES_DB: str = "mini_loan_marketplace"
    POSTGRES_USER: str = "marketplace_user"
    POSTGRES_PASSWORD: str = "local_dev_password_change_me"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

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
