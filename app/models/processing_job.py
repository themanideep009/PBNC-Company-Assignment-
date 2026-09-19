"""Processing job model — tracks each stage of the document processing pipeline."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PipelineStage:
    VALIDATION = "VALIDATION"
    PREPROCESSING = "PREPROCESSING"
    EXTRACTION = "EXTRACTION"
    SEGMENTATION = "SEGMENTATION"
    ANSWER_KEY = "ANSWER_KEY"
    CONFIDENCE = "CONFIDENCE"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobStatus.PENDING
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    log: Mapped[dict] = mapped_column(
        JSONB, nullable=True, default=dict,
        comment="Structured log: timings, error details, metrics"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    # Relationships
    document = relationship("Document", back_populates="processing_jobs")
