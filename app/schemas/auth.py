"""Auth schemas — registration, login, and token responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Registration request body."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT access token response."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user information."""
    id: UUID
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
