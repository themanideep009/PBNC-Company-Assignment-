"""
Questions API — get individual questions and their answers.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.document import Document
from app.models.question import Question
from app.models.user import User
from app.schemas.question import QuestionResponse, OptionResponse, AnswerResponse

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.get(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Get a single question with full details",
)
def get_question(
    question_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetch a single question by ID with the full structured output
    matching the Section 4 contract.

    Verifies document ownership — returns 404 if user doesn't own the
    parent document (prevents existence leakage).
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    # Verify ownership via the parent document
    document = db.query(Document).filter(
        Document.id == question.document_id,
        Document.owner_id == current_user.id,
    ).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    options = [
        OptionResponse(label=o.label, text=o.text, image_url=o.image_path)
        for o in sorted(question.options, key=lambda o: o.sort_order)
    ]

    answer = None
    if question.answer:
        answer = AnswerResponse(
            value=question.answer.answer_value,
            source=question.answer.source,
            match_confidence=question.answer.match_confidence,
            review_required=question.answer.review_required,
        )

    return QuestionResponse(
        question_id=question.id,
        document_id=question.document_id,
        question_number=question.question_number,
        question_text=question.question_text,
        question_type=question.question_type,
        options=options,
        answer=answer,
        source_pages=question.source_pages,
        extraction_confidence=question.extraction_confidence,
        review_required=question.review_required,
        review_reason=question.review_reason,
        images=[],
        created_at=question.created_at,
    )


@router.get(
    "/{question_id}/answer",
    response_model=AnswerResponse,
    summary="Get the answer for a question",
)
def get_question_answer(
    question_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get just the answer portion for a question.

    Returns 404 if no answer is associated.
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    # Verify ownership
    document = db.query(Document).filter(
        Document.id == question.document_id,
        Document.owner_id == current_user.id,
    ).first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if question.answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No answer found for this question",
        )

    return AnswerResponse(
        value=question.answer.answer_value,
        source=question.answer.source,
        match_confidence=question.answer.match_confidence,
        review_required=question.answer.review_required,
    )
