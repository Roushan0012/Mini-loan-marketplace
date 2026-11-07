from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class UserRegisterRequest(BaseModel):
    """Payload for customer account registration."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=2, max_length=150, description="Customer full name")
    email: EmailStr = Field(..., description="Customer email address")
    password: SecretStr = Field(..., min_length=12, max_length=128, description="Account password")


class UserLoginRequest(BaseModel):
    """Payload for user login authentication."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., description="Registered account email")
    password: SecretStr = Field(..., description="Account password")


class UserPublicResponse(BaseModel):
    """Public representation of a user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Bearer token authentication response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
