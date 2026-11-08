from collections.abc import Callable
from typing import Set

from fastapi import Depends, HTTPException, status

from app.core.auth_dependencies import get_current_user
from app.models.user import User


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """Factory creating a FastAPI dependency to enforce permitted user roles.

    Enforces:
    - Current authenticated and active user retrieval from database via get_current_user.
    - Role validation against allowed_roles whitelist.
    - Generic HTTP 403 Forbidden on role mismatch.
    - Strict reliance on PostgreSQL database user record (never client-provided roles).
    """
    permitted_roles: Set[str] = set(allowed_roles)

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in permitted_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient permissions.",
            )
        return current_user

    return role_checker


# Reusable role-specific dependencies
require_customer = require_roles("customer")
require_caller = require_roles("caller")
require_admin = require_roles("admin")
