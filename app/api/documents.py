"""
Document API — upload, status, listing, linking, page image retrieval.

Security notes:
- Upload does only cheap synchronous checks (MIME sniff, hard size check)
- Compression and extraction happen in the async worker pipeline
- Every fetch verifies document ownership (returns 404 not 403 for non-owners)
- Page images served through authenticated streaming endpoint, never static files
"""

import io
import logging
import uuid
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, verify_document_owner
from app.models.document import Document, DocumentStatus, DocumentRole
from app.models.document_link import DocumentLink, RelationType
from app.models.page import Page
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentStatusResponse,
    DocumentListItem,
    DocumentLinkRequest,
    DocumentLinkResponse,
    ProcessingJobResponse,
)
from app.services.file_validator import FileValidator, FileValidationError
from app.services.rate_limiter import RateLimiter, RateLimitExceeded
from app.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for processing",
)
async def upload_document(
    file: UploadFile = File(...),
    doc_role: str = Form(default="UNSPECIFIED"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF or image document for async processing.

    Returns immediately with document_id and status=QUEUED.
    The actual processing happens in the Celery worker pipeline.

    Synchronous checks performed here:
    1. Rate limit check (Redis token bucket)
    2. MIME type validation (content sniffing via libmagic)
    3. Hard size limit check

    Everything else (compression, extraction) happens async in the worker.
    """
    # Rate limit check
    try:
        rate_limiter = RateLimiter()
        rate_limiter.check_rate_limit(str(current_user.id))
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Upload rate limit exceeded. Retry after {e.retry_after} seconds.",
            headers={"Retry-After": str(e.retry_after)},
        )

    # Read file content
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Validate MIME type and size (cheap sync checks only)
    validator = FileValidator()
    try:
        detected_mime, needs_compression = validator.validate_upload(
            file_bytes, file.filename or "unknown"
        )
    except FileValidationError as e:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if e.error_code == "FILE_TOO_LARGE"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=e.message)

    # Validate doc_role
    valid_roles = [DocumentRole.QUESTION_PAPER, DocumentRole.ANSWER_KEY, DocumentRole.UNSPECIFIED]
    if doc_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid doc_role. Must be one of: {valid_roles}",
        )

    # Store original file with UUID-based path (never uses client filename)
    storage = get_storage_service()
    file_ext = _safe_extension(detected_mime)
    storage_filename = f"{uuid.uuid4()}{file_ext}"
    storage_path = storage.save_bytes(file_bytes, "raw", storage_filename)

    # Sanitize the original filename for display only
    safe_filename = _sanitize_filename(file.filename or "unnamed")

    # Create document record
    document = Document(
        owner_id=current_user.id,
        filename=safe_filename,
        storage_path=storage_path,
        mime_type=detected_mime,
        original_size_bytes=file_size,
        status=DocumentStatus.QUEUED,
        doc_role=doc_role,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Enqueue for async processing
    try:
        from app.workers.tasks import process_document
        process_document.delay(str(document.id))
        logger.info(f"Document {document.id} queued for processing")
    except Exception as e:
        logger.error(f"Failed to enqueue document {document.id}: {e}")
        document.status = DocumentStatus.FAILED
        document.error_message = "Failed to enqueue for processing"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue document for processing",
        )

    upload_message = (
        f"Document uploaded and queued. Large file ({file_size / (1024*1024):.1f} MB) exceeds standard threshold; "
        f"automatic background compression and dimension constraining will be applied."
        if needs_compression
        else "Document uploaded and queued for processing"
    )

    return DocumentUploadResponse(
        document_id=document.id,
        filename=safe_filename,
        status=document.status,
        message=upload_message,
        needs_compression=needs_compression,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Get document processing status",
)
def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current processing status of a document, including compression info."""
    document = verify_document_owner(document_id, current_user, db)

    response = DocumentStatusResponse.model_validate(document)
    # Add computed size fields
    if document.original_size_bytes:
        response.original_size_mb = round(document.original_size_bytes / (1024 * 1024), 2)
    if document.stored_size_bytes:
        response.processed_size_mb = round(document.stored_size_bytes / (1024 * 1024), 2)

    return response


@router.get(
    "",
    response_model=PaginatedResponse[DocumentListItem],
    summary="List user's documents",
)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    role_filter: Optional[str] = Query(None, alias="doc_role"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List documents owned by the current user, with optional filters."""
    query = db.query(Document).filter(Document.owner_id == current_user.id)

    if status_filter:
        query = query.filter(Document.status == status_filter)
    if role_filter:
        query = query.filter(Document.doc_role == role_filter)

    total = query.count()
    offset = (page - 1) * page_size
    documents = query.order_by(Document.created_at.desc()).offset(offset).limit(page_size).all()

    return PaginatedResponse(
        items=[DocumentListItem.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.post(
    "/{document_id}/link",
    response_model=DocumentLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link an answer key to a question paper",
)
def link_documents(
    document_id: uuid.UUID,
    body: DocumentLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Link two documents (e.g., associate an answer key with a question paper).

    Both documents must be owned by the current user.
    After linking, the system will attempt to match answers to questions.
    """
    # Verify ownership of both documents
    document = verify_document_owner(document_id, current_user, db)
    linked_document = verify_document_owner(body.linked_document_id, current_user, db)

    # Prevent self-linking
    if document_id == body.linked_document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot link a document to itself",
        )

    # Check for existing link
    existing = db.query(DocumentLink).filter(
        DocumentLink.document_id == document_id,
        DocumentLink.linked_document_id == body.linked_document_id,
        DocumentLink.relation_type == body.relation_type,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document link already exists",
        )

    link = DocumentLink(
        document_id=document_id,
        linked_document_id=body.linked_document_id,
        relation_type=body.relation_type,
    )
    db.add(link)

    # Update doc_roles if linking as answer key
    if body.relation_type == RelationType.ANSWER_KEY_FOR:
        if linked_document.doc_role == DocumentRole.UNSPECIFIED:
            linked_document.doc_role = DocumentRole.ANSWER_KEY
        if document.doc_role == DocumentRole.UNSPECIFIED:
            document.doc_role = DocumentRole.QUESTION_PAPER

    db.commit()
    db.refresh(link)

    # Trigger answer key re-processing if both documents are already processed
    if (
        document.status == DocumentStatus.COMPLETED
        and linked_document.status == DocumentStatus.COMPLETED
    ):
        try:
            from app.workers.tasks import process_answer_key_linking
            process_answer_key_linking.delay(str(document_id), str(body.linked_document_id))
        except Exception as e:
            logger.warning(f"Failed to trigger answer key re-processing: {e}")

    return DocumentLinkResponse.model_validate(link)


@router.get(
    "/{document_id}/questions",
    summary="Get questions extracted from a document",
)
def get_document_questions(
    document_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get paginated list of questions extracted from a document."""
    document = verify_document_owner(document_id, current_user, db)

    from app.models.question import Question

    query = db.query(Question).filter(Question.document_id == document_id)
    total = query.count()
    offset = (page - 1) * page_size
    questions = query.order_by(Question.question_number).offset(offset).limit(page_size).all()

    from app.schemas.question import QuestionResponse, OptionResponse, AnswerResponse

    items = []
    for q in questions:
        options = [
            OptionResponse(label=o.label, text=o.text, image_url=o.image_path)
            for o in sorted(q.options, key=lambda o: o.sort_order)
        ]
        answer = None
        if q.answer:
            answer = AnswerResponse(
                value=q.answer.answer_value,
                source=q.answer.source,
                match_confidence=q.answer.match_confidence,
                review_required=q.answer.review_required,
            )
        items.append(
            QuestionResponse(
                question_id=q.id,
                document_id=q.document_id,
                question_number=q.question_number,
                question_text=q.question_text,
                question_type=q.question_type,
                options=options,
                answer=answer,
                source_pages=q.source_pages,
                extraction_confidence=q.extraction_confidence,
                review_required=q.review_required,
                review_reason=q.review_reason,
                images=[],
                created_at=q.created_at,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{document_id}/pages/{page_number}/image",
    summary="Get page image (auth-gated)",
)
def get_page_image(
    document_id: uuid.UUID,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream a page image through an authenticated endpoint.

    Security: files are NEVER served as static content.
    Every request requires a valid JWT and document ownership verification.
    """
    document = verify_document_owner(document_id, current_user, db)

    page = db.query(Page).filter(
        Page.document_id == document_id,
        Page.page_number == page_number,
    ).first()

    if page is None or page.image_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page image not found",
        )

    storage = get_storage_service()
    try:
        image_bytes = storage.read(page.image_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page image file not found on storage",
        )

    return StreamingResponse(
        io.BytesIO(image_bytes),
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=page_{page_number}.png"},
    )


@router.get(
    "/{document_id}/jobs",
    response_model=list[ProcessingJobResponse],
    summary="Get processing job history for a document",
)
def get_document_jobs(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the processing job history (pipeline stages) for a document."""
    document = verify_document_owner(document_id, current_user, db)

    jobs = db.query(ProcessingJob).filter(
        ProcessingJob.document_id == document_id,
    ).order_by(ProcessingJob.created_at).all()

    return [ProcessingJobResponse.model_validate(j) for j in jobs]


# ── Helper Functions ──────────────────────────────────────────────────────


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize a client-supplied filename for display purposes only.
    Strips path components to prevent directory traversal display issues.
    Never used for storage path generation.
    """
    import os
    # Remove any path components
    name = os.path.basename(filename)
    # Remove null bytes and control characters
    name = "".join(c for c in name if c.isprintable() and c != "\x00")
    # Truncate to reasonable length
    if len(name) > 255:
        name = name[:255]
    return name or "unnamed"


def _safe_extension(mime_type: str) -> str:
    """Map MIME type to safe file extension."""
    extensions = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }
    return extensions.get(mime_type, "")
