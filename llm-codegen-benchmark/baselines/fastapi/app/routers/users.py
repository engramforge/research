"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User, UserCreate, UserResponse

router = APIRouter()

# In-memory storage for demo
_users_db: dict[int, User] = {}
_next_id = 1


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_create: UserCreate) -> UserResponse:
    """Create a new user."""
    global _next_id

    # Check for duplicate email
    for existing_user in _users_db.values():
        if existing_user.email == user_create.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Create user (simple hash for demo)
    user = User(
        id=_next_id,
        email=user_create.email,
        name=user_create.name,
        hashed_password=f"hashed_{user_create.password}",
    )
    _users_db[_next_id] = user
    _next_id += 1

    return UserResponse(id=user.id, email=user.email, name=user.name)


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current user info."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int) -> UserResponse:
    """Get user by ID."""
    user = _users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(id=user.id, email=user.email, name=user.name)
