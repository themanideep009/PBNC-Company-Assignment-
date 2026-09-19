"""
Review queue API — list flagged items and mark them resolved.
"""

import uuid
from math import ceil
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.document import Document
from app.models.review_item import ReviewItem
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.review import ReviewItemResponse, ReviewItemResolveRequest

router = APIRouter(prefix="/review-queue", tags=["Review Queue"])


@router.get(
    "",
    response_model=PaginatedResponse[ReviewItemResponse],
    summary="List review queue items",
)
def list_review_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List review-flagged items for the current user's documents.

    Filterable by entity_type (QUESTION/ANSWER/DOCUMENT), severity, and resolved status.
    Only shows items from documents owned by the current user.
    """
    # Get user's document IDs for ownership filtering
    user_doc_ids = db.query(Document.id).filter(
        Document.owner_id == current_user.id
    ).subquery()

    query = db.query(ReviewItem).filter(
        ReviewItem.document_id.in_(user_doc_ids)
    )

    if entity_type:
        query = query.filter(ReviewItem.entity_type == entity_type)
    if severity:
        query = query.filter(ReviewItem.severity == severity)
    if resolved is not None:
        query = query.filter(ReviewItem.resolved == resolved)

    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(ReviewItem.created_at.desc()).offset(offset).limit(page_size).all()

    return PaginatedResponse(
        items=[ReviewItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.patch(
    "/{review_item_id}",
    response_model=ReviewItemResponse,
    summary="Resolve a review item",
)
def resolve_review_item(
    review_item_id: uuid.UUID,
    body: ReviewItemResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a review item as resolved (human-in-the-loop correction).

    Only the owner of the parent document can resolve review items.
    """
    review_item = db.query(ReviewItem).filter(
        ReviewItem.id == review_item_id
    ).first()

    if review_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )

    # Verify ownership via parent document
    document = db.query(Document).filter(
        Document.id == review_item.document_id,
        Document.owner_id == current_user.id,
    ).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )

    review_item.resolved = body.resolved
    review_item.resolved_by = current_user.id
    review_item.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(review_item)

    return ReviewItemResponse.model_validate(review_item)
