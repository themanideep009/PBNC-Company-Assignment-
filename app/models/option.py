"""Option model — choices for MCQ-type questions."""

import uuid

from sqlalchemy import String, Text, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Option(Base):
    __tablename__ = "options"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Option label: A, B, C, D or 1, 2, 3, 4"
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str] = mapped_column(String(1000), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    question = relationship("Question", back_populates="options")
