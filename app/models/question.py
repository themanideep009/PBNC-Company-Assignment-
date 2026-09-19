"""Question model — extracted questions from documents."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, Float, Boolean, ForeignKey, text, DateTime, Integer
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuestionType:
    MCQ = "MCQ"
    SHORT = "SHORT"
    LONG = "LONG"
    TRUE_FALSE = "TRUE_FALSE"
    UNKNOWN = "UNKNOWN"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    question_number: Mapped[str] = mapped_column(
        String(50), nullable=True,
        comment="As detected in the document, may be '1', '1a', 'Q.1', etc."
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QuestionType.UNKNOWN
    )
    source_pages: Mapped[list] = mapped_column(
        ARRAY(Integer), nullable=True,
        comment="Page numbers where this question appears"
    )
    extraction_confidence: Mapped[float] = mapped_column(
        Float, nullable=True, default=0.0,
        comment="Composite confidence score 0.0-1.0"
    )
    review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    review_reason: Mapped[str] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(
        Text, nullable=True,
        comment="Original OCR/extracted text before any cleanup"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    # Relationships
    document = relationship("Document", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")
    answer = relationship("Answer", back_populates="question", uselist=False, cascade="all, delete-orphan")
