"""Answer model — answer values associated with questions."""

import uuid

from sqlalchemy import String, Text, Float, Boolean, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AnswerSource:
    SAME_DOC = "SAME_DOC"
    LINKED_DOC = "LINKED_DOC"
    NONE_FOUND = "NONE_FOUND"


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False, unique=True
    )
    answer_value: Mapped[str] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AnswerSource.NONE_FOUND
    )
    match_confidence: Mapped[float] = mapped_column(
        Float, nullable=True, default=0.0,
        comment="How confident we are the answer matches the correct question"
    )
    review_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    # Relationships
    question = relationship("Question", back_populates="answer")
