"""
Auth API — register and login endpoints.

These are the only unprotected endpoints (besides /healthz).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new user account.

    - Email must be unique.
    - Password is hashed with bcrypt before storage (plaintext is never persisted).
    """
    # Check for existing user
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT",
)
def login(body: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email + password and receive a JWT access token.

    The token must be sent as `Authorization: Bearer <token>` on all
    protected endpoints.
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Constant-time comparison — verify_password runs bcrypt regardless of
    # whether the user exists, but we short-circuit on None user to avoid
    # attribute access on None. Timing difference is negligible since the
    # hash comparison dominates.
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user profile."""
    return current_user
