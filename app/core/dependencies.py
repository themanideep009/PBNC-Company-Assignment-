"""
FastAPI dependencies for authentication, database sessions, and authorization.

Every protected endpoint uses get_current_user to extract and validate the JWT,
then look up the user in the database. Ownership checks use verify_document_owner.
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.document import Document

# HTTP Bearer scheme — extracts "Authorization: Bearer <token>"
security_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract JWT from Authorization header, decode, and fetch the user.
    Returns 401 if token is invalid/expired or user not found.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def verify_document_owner(
    document_id: uuid.UUID,
    current_user: User,
    db: Session,
) -> Document:
    """
    Fetch a document and verify the current user owns it.
    Returns 404 (not 403) to avoid existence leakage per security requirements.
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.owner_id == current_user.id,
    ).first()

    if document is None:
        # Return 404 regardless of whether the doc exists but belongs to
        # another user — prevents existence leakage (Section 8 requirement)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document
