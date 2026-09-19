"""Question & answer schemas — structured output per Section 4 contract."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class OptionResponse(BaseModel):
    """Single option for an MCQ question."""
    label: str
    text: str
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AnswerResponse(BaseModel):
    """Answer associated with a question."""
    value: Optional[str] = None
    source: str
    match_confidence: Optional[float] = None
    review_required: bool = False

    model_config = {"from_attributes": True}


class QuestionResponse(BaseModel):
    """
    Full structured question output — matches the contract in Section 4.
    This is the primary data product of the extraction pipeline.
    """
    question_id: UUID
    document_id: UUID
    question_number: Optional[str] = None
    question_text: str
    question_type: str
    options: List[OptionResponse] = []
    answer: Optional[AnswerResponse] = None
    source_pages: Optional[List[int]] = None
    extraction_confidence: Optional[float] = None
    review_required: bool = False
    review_reason: Optional[str] = None
    images: List[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionListItem(BaseModel):
    """Summary item for question listing."""
    question_id: UUID
    question_number: Optional[str] = None
    question_text: str
    question_type: str
    extraction_confidence: Optional[float] = None
    review_required: bool = False
    source_pages: Optional[List[int]] = None

    model_config = {"from_attributes": True}
