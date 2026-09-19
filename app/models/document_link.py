"""Document linking — relates answer keys to question papers."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RelationType:
    ANSWER_KEY_FOR = "ANSWER_KEY_FOR"
    SUPPLEMENT_OF = "SUPPLEMENT_OF"


class DocumentLink(Base):
    __tablename__ = "document_links"
    __table_args__ = (
        UniqueConstraint("document_id", "linked_document_id", "relation_type",
                         name="uq_document_link"),
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
    linked_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    # Relationships
    document = relationship(
        "Document", foreign_keys=[document_id], back_populates="links_from"
    )
    linked_document = relationship(
        "Document", foreign_keys=[linked_document_id], back_populates="links_to"
    )
