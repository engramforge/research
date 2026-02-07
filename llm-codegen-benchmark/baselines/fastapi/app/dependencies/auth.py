"""Authentication dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.user import User

security = HTTPBearer()

# Demo user for testing
_demo_user = User(
    id=0,
    email="demo@example.com",
    name="Demo User",
    hashed_password="hashed_demo",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Get current user from bearer token.

    For demo purposes, accepts any token starting with "valid_".
    In production, this would validate JWT tokens.
    """
    token = credentials.credentials

    if not token.startswith("valid_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return demo user for valid tokens
    return _demo_user
