"""
Pipeline Stage 5: Answer Key Detection & Association.

Handles:
- Detecting answer keys within the same document (e.g., at the end)
- Cross-document linking (when an answer key doc is linked to a question paper)
- Pattern matching for common answer key formats
- Fuzzy matching of answers to questions by number
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.workers.pipeline.stage4_segmentation import ExtractedQuestion

logger = logging.getLogger(__name__)


@dataclass
class ExtractedAnswer:
    """An answer matched to a question."""
    question_number: str
    answer_value: str
    source: str  # "SAME_DOC", "LINKED_DOC"
    match_type: str  # "exact", "fuzzy", "positional"
    match_confidence: float  # 0.0-1.0


# ── Answer Key Patterns ──────────────────────────────────────────────────
# Common formats: "1. B", "Q1: B", "1-B", "1) B", "(1) B"
ANSWER_KEY_PATTERNS = [
    # "1. B" or "1. Answer text"
    re.compile(r"^\s*(\d{1,3})\.\s*([A-Da-d])\s*$", re.MULTILINE),
    # "Q1: B" / "Q.1: B"
    re.compile(r"^\s*Q\.?\s*(\d{1,3})\s*[:=]\s*([A-Da-d])\s*$", re.MULTILINE | re.IGNORECASE),
    # "1-B" / "1 - B"
    re.compile(r"^\s*(\d{1,3})\s*[-–—]\s*([A-Da-d])\s*$", re.MULTILINE),
    # "1) B"
    re.compile(r"^\s*(\d{1,3})\)\s*([A-Da-d])\s*$", re.MULTILINE),
    # "(1) B"
    re.compile(r"^\s*\((\d{1,3})\)\s*([A-Da-d])\s*$", re.MULTILINE),
    # Tabular: "1    B" (multiple spaces/tabs)
    re.compile(r"^\s*(\d{1,3})\s{2,}([A-Da-d])\s*$", re.MULTILINE),
    # Longer answers: "1. answer text here"
    re.compile(r"^\s*(\d{1,3})\.\s+(.{1,200}?)\s*$", re.MULTILINE),
]

# Pattern to detect "Answer Key" section header
ANSWER_SECTION_HEADERS = re.compile(
    r"(?:answer\s*key|answers?|solution\s*key|solutions?|marking\s*scheme)",
    re.IGNORECASE,
)


def run_stage5(
    questions: List[ExtractedQuestion],
    page_data_list: List[dict],
    linked_doc_text: Optional[str] = None,
) -> Dict[str, ExtractedAnswer]:
    """
    Execute Stage 5: Answer Key Detection & Association.

    Args:
        questions: Extracted questions from Stage 4
        page_data_list: Page data with text from Stage 3
        linked_doc_text: Text from a linked answer key document (if any)

    Returns:
        Dict mapping question_number → ExtractedAnswer
    """
    answers: Dict[str, ExtractedAnswer] = {}

    # Strategy 1: Look for answers in the same document
    combined_text = "\n".join(
        p.get("ocr_text", "") or "" for p in page_data_list
    )
    same_doc_answers = _find_answer_key_in_text(combined_text, "SAME_DOC")

    if same_doc_answers:
        logger.info(f"Found {len(same_doc_answers)} answers in same document")
        answers.update(same_doc_answers)

    # Strategy 2: Look for answers in linked document
    if linked_doc_text:
        linked_answers = _find_answer_key_in_text(linked_doc_text, "LINKED_DOC")
        if linked_answers:
            logger.info(f"Found {len(linked_answers)} answers in linked document")
            # Linked doc answers take precedence over same-doc
            answers.update(linked_answers)

    # Strategy 3: Match answers to questions
    matched_answers = _match_answers_to_questions(questions, answers)

    return matched_answers


def _find_answer_key_in_text(text: str, source: str) -> Dict[str, ExtractedAnswer]:
    """
    Search for answer key patterns in text.

    Tries to find a dedicated "Answer Key" section first,
    then falls back to scanning the entire text.
    """
    answers = {}

    # Check for an answer key section
    section_match = ANSWER_SECTION_HEADERS.search(text)
    search_text = text

    if section_match:
        # Only search from the answer key header onwards
        search_text = text[section_match.start():]
        logger.debug("Found answer key section header")

    # Try each answer key pattern
    best_pattern_answers = {}

    for pattern in ANSWER_KEY_PATTERNS:
        matches = list(pattern.finditer(search_text))
        if len(matches) > len(best_pattern_answers):
            pattern_answers = {}
            for m in matches:
                q_num = m.group(1)
                answer_val = m.group(2).strip().upper()
                pattern_answers[q_num] = ExtractedAnswer(
                    question_number=q_num,
                    answer_value=answer_val,
                    source=source,
                    match_type="exact",
                    match_confidence=0.95 if section_match else 0.80,
                )
            best_pattern_answers = pattern_answers

    answers.update(best_pattern_answers)
    return answers


def _match_answers_to_questions(
    questions: List[ExtractedQuestion],
    raw_answers: Dict[str, ExtractedAnswer],
) -> Dict[str, ExtractedAnswer]:
    """
    Match extracted answers to questions.

    Matching strategy (in order of confidence):
    1. Exact question number match → high confidence
    2. Fuzzy number match (e.g., "1a" matches "1") → medium confidence
    3. Positional match (nth answer → nth question) → low confidence
    """
    matched = {}

    # Build a lookup of question numbers
    q_numbers = {}
    for i, q in enumerate(questions):
        if q.question_number:
            q_numbers[q.question_number] = q
            # Also index by pure numeric part for fuzzy matching
            numeric = re.sub(r"[^0-9]", "", q.question_number)
            if numeric and numeric not in q_numbers:
                q_numbers[numeric] = q

    # Exact matching
    for q_num, answer in raw_answers.items():
        if q_num in q_numbers:
            matched[q_num] = answer
            matched[q_num].match_type = "exact"
        else:
            # Try numeric-only matching
            numeric = re.sub(r"[^0-9]", "", q_num)
            if numeric in q_numbers:
                matched[q_numbers[numeric].question_number or numeric] = ExtractedAnswer(
                    question_number=q_numbers[numeric].question_number or numeric,
                    answer_value=answer.answer_value,
                    source=answer.source,
                    match_type="fuzzy",
                    match_confidence=answer.match_confidence * 0.8,  # Reduce for fuzzy
                )

    # Positional matching for unmatched questions (last resort)
    unmatched_questions = [
        q for q in questions
        if q.question_number and q.question_number not in matched
    ]
    unmatched_answers = [
        a for q_num, a in raw_answers.items()
        if q_num not in matched and q_num not in [
            re.sub(r"[^0-9]", "", m) for m in matched
        ]
    ]

    if unmatched_questions and unmatched_answers:
        for q, a in zip(unmatched_questions, unmatched_answers):
            if q.question_number:
                matched[q.question_number] = ExtractedAnswer(
                    question_number=q.question_number,
                    answer_value=a.answer_value,
                    source=a.source,
                    match_type="positional",
                    match_confidence=0.5,
                )

    return matched


def get_linked_document_text(document_id: str, db_session) -> Optional[str]:
    """
    Fetch text from linked answer key documents.

    This is called from the main task when a document has linked answer keys.
    """
    from app.models.document_link import DocumentLink, RelationType
    from app.models.page import Page

    # Find linked answer key documents
    links = db_session.query(DocumentLink).filter(
        DocumentLink.document_id == document_id,
        DocumentLink.relation_type == RelationType.ANSWER_KEY_FOR,
    ).all()

    if not links:
        return None

    # Combine text from all linked answer key pages
    all_text = []
    for link in links:
        pages = db_session.query(Page).filter(
            Page.document_id == link.linked_document_id
        ).order_by(Page.page_number).all()

        for page in pages:
            text = page.ocr_text or page.native_text or ""
            if text.strip():
                all_text.append(text)

    return "\n".join(all_text) if all_text else None
