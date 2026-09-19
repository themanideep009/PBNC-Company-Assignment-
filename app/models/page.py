"""Page model — individual pages extracted from documents."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, Text, Float, ForeignKey, text,
    UniqueConstraint, DateTime
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_page_doc_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str] = mapped_column(String(1000), nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=True)
    native_text: Mapped[str] = mapped_column(Text, nullable=True)
    rotation_applied: Mapped[float] = mapped_column(Float, nullable=True, default=0.0)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    quality_flags: Mapped[dict] = mapped_column(
        JSONB, nullable=True, default=dict,
        comment="Flags like low_contrast, heavy_noise, skew_detected, etc."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    # Relationships
    document = relationship("Document", back_populates="pages")
