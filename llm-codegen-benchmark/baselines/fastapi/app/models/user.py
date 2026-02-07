"""User models."""

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user model."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    """User creation request model."""

    password: str = Field(min_length=8, max_length=100)


class User(UserBase):
    """Internal user model."""

    id: int
    hashed_password: str


class UserResponse(UserBase):
    """User response model (no password)."""

    id: int

    model_config = {"from_attributes": True}
