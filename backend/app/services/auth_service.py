from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User


class DuplicateEmailError(ValueError):
    """Raised when attempting to register an account with an existing email."""

    pass


def register_customer(
    db: Session,
    full_name: str,
    email: str,
    password: str,
) -> User:
    """Register a new customer account.

    Always enforces role='customer' and is_active=True on the server.
    Normalizes email (strip + lower) and stores password only as an Argon2 hash.
    """
    normalized_email = email.strip().lower()

    # Pre-check for duplicate email
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user is not None:
        raise DuplicateEmailError("An account with this email address already exists.")

    hashed_pw = hash_password(password)

    new_user = User(
        full_name=full_name.strip(),
        email=normalized_email,
        password_hash=hashed_pw,
        role="customer",  # Always assigned on the server
        is_active=True,
    )

    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError as exc:
        db.rollback()
        # Handle concurrent registration collisions
        raise DuplicateEmailError("An account with this email address already exists.") from exc


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> Optional[User]:
    """Authenticate a user by email and password.

    Returns the User record on successful authentication.
    Returns None for unknown email, incorrect password, or inactive accounts
    without leaking which condition failed.
    """
    normalized_email = email.strip().lower()

    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_active:
        return None

    return user
