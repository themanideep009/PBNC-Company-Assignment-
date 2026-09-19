"""Document model — uploaded files and their processing status."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, DateTime, Integer, BigInteger, Text, ForeignKey, text, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentStatus:
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentRole:
    QUESTION_PAPER = "QUESTION_PAPER"
    ANSWER_KEY = "ANSWER_KEY"
    UNSPECIFIED = "UNSPECIFIED"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_owner_status", "owner_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="Original client-supplied filename (sanitized, for display only)"
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000), nullable=False,
        comment="Server-generated UUID-based path, never derived from client filename"
    )
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stored_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocumentStatus.UPLOADED, index=True
    )
    doc_role: Mapped[str] = mapped_column(
        String(30), nullable=False, default=DocumentRole.UNSPECIFIED
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    compression_applied: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    pages_processed: Mapped[int] = mapped_column(Integer, nullable=True)
    pages_skipped: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    # Relationships
    owner = relationship("User", back_populates="documents")
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")
    links_from = relationship(
        "DocumentLink",
        foreign_keys="DocumentLink.document_id",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    links_to = relationship(
        "DocumentLink",
        foreign_keys="DocumentLink.linked_document_id",
        back_populates="linked_document",
    )
