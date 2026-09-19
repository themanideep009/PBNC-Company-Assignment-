"""Document schemas — upload, status, listing, linking."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload + queue."""
    document_id: UUID
    filename: str
    status: str
    message: str
    needs_compression: bool = False


class DocumentStatusResponse(BaseModel):
    """Detailed document processing status."""
    id: UUID
    filename: str
    status: str
    doc_role: str
    mime_type: str
    original_size_bytes: int
    stored_size_bytes: Optional[int] = None
    compression_applied: bool = False
    original_size_mb: Optional[float] = None
    processed_size_mb: Optional[float] = None
    page_count: Optional[int] = None
    pages_processed: Optional[int] = None
    pages_skipped: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    """Summary item for document listing."""
    id: UUID
    filename: str
    status: str
    doc_role: str
    mime_type: str
    page_count: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentLinkRequest(BaseModel):
    """Request to link two documents."""
    linked_document_id: UUID
    relation_type: str = Field(
        ...,
        pattern=r"^(ANSWER_KEY_FOR|SUPPLEMENT_OF)$",
        description="ANSWER_KEY_FOR or SUPPLEMENT_OF",
    )


class DocumentLinkResponse(BaseModel):
    """Response after linking documents."""
    id: UUID
    document_id: UUID
    linked_document_id: UUID
    relation_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProcessingJobResponse(BaseModel):
    """Processing job status for a pipeline stage."""
    id: UUID
    stage: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    log: Optional[dict] = None

    model_config = {"from_attributes": True}
