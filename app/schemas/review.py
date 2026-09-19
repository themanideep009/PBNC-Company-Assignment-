"""Review queue schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ReviewItemResponse(BaseModel):
    """Review queue item."""
    id: UUID
    document_id: UUID
    entity_type: str
    entity_id: UUID
    reason: str
    severity: str
    resolved: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewItemResolveRequest(BaseModel):
    """Request to resolve a review item."""
    resolved: bool = True
    notes: Optional[str] = None
