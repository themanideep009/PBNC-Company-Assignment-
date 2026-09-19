"""
Pipeline Stage 4: Question Segmentation.

Segments extracted text into individual questions using:
- Regex-based question number detection (Q.1, 1., 1), Question 1, etc.)
- Option detection (A., (A), a), etc.)
- Question type classification (MCQ, TRUE_FALSE, SHORT, LONG)
- Multi-page stitching for questions spanning page boundaries

No LLM dependency — pure regex + heuristics (LLM adapter is a fallback stub).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.adapters.llm_adapter import get_llm_adapter

logger = logging.getLogger(__name__)


# ── Question Number Patterns ──────────────────────────────────────────────
# Ordered from most specific to least specific to reduce false positives
QUESTION_PATTERNS = [
    # "Question 1" / "Q.1" / "Q 1" / "Ques. 1" / "Ques 1"
    re.compile(r"^(?:Question|Ques\.?|Q\.?)\s*(\d+)\b", re.IGNORECASE | re.MULTILINE),
    # "1." at start of line (with possible whitespace)
    re.compile(r"^\s*(\d{1,3})\.\s+\S", re.MULTILINE),
    # "1)" at start of line
    re.compile(r"^\s*(\d{1,3})\)\s+\S", re.MULTILINE),
    # "(1)" at start of line
    re.compile(r"^\s*\((\d{1,3})\)\s+\S", re.MULTILINE),
    # Roman numerals: "i.", "ii.", "iii." etc.
    re.compile(r"^\s*((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)+)\.\s+\S", re.IGNORECASE | re.MULTILINE),
]

# ── Option Patterns ───────────────────────────────────────────────────────
OPTION_PATTERNS = [
    # "(A)" / "(a)"
    re.compile(r"^\s*\(([A-Da-d])\)\s*(.*)", re.MULTILINE),
    # "A." / "a."
    re.compile(r"^\s*([A-Da-d])\.\s+(.*)", re.MULTILINE),
    # "A)" / "a)"
    re.compile(r"^\s*([A-Da-d])\)\s*(.*)", re.MULTILINE),
    # "(1)" / "(2)" for numbered options (less common)
    re.compile(r"^\s*\(([1-4])\)\s*(.*)", re.MULTILINE),
]

# ── True/False Pattern ────────────────────────────────────────────────────
TRUE_FALSE_PATTERN = re.compile(
    r"\b(?:true\s*(?:or|/)\s*false|T\s*(?:or|/)\s*F|state\s+(?:true|false))\b",
    re.IGNORECASE,
)

# ── Marks/Space Indicators (for SHORT/LONG classification) ────────────────
MARKS_PATTERN = re.compile(r"\[(\d+)\s*(?:marks?|pts?|points?)\]", re.IGNORECASE)
SHORT_INDICATORS = re.compile(
    r"\b(?:one\s+word|one\s+sentence|briefly|short\s+answer|define|name|state)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedOption:
    """A single option extracted from a question."""
    label: str
    text: str
    image_path: Optional[str] = None


@dataclass
class ExtractedQuestion:
    """A question extracted from the document text."""
    question_number: Optional[str] = None
    question_text: str = ""
    question_type: str = "UNKNOWN"
    options: List[ExtractedOption] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)
    raw_text: str = ""
    number_detected_by: str = "none"  # "regex" or "positional" — for confidence scoring


def run_stage4(page_data_list: List[dict]) -> List[ExtractedQuestion]:
    """
    Execute Stage 4: Question Segmentation.

    Args:
        page_data_list: Pages with extracted text from Stage 3.

    Returns:
        List of ExtractedQuestion objects.
    """
    # Combine all page texts with page markers
    page_texts = []
    for page_data in page_data_list:
        text = page_data.get("ocr_text", "") or ""
        page_num = page_data["page_number"]
        page_texts.append((page_num, text))

    # Find question boundaries across all pages
    questions = _segment_questions(page_texts)

    # Classify question types and extract options
    for q in questions:
        q.options = _extract_options(q.question_text)
        q.question_type = _classify_question_type(q.question_text, q.options)

        # Clean question text (remove option text from main question)
        if q.options:
            q.question_text = _clean_question_text(q.question_text, q.options)

    logger.info(f"Segmented {len(questions)} questions from {len(page_data_list)} pages")

    # If no questions found via regex, try LLM assist (stub returns None)
    if not questions and page_texts:
        combined_text = "\n".join(t for _, t in page_texts)
        llm = get_llm_adapter()
        llm_result = llm.segment_text(combined_text)
        if llm_result:
            for qd in llm_result.questions:
                questions.append(ExtractedQuestion(
                    question_number=qd.get("question_number"),
                    question_text=qd.get("question_text", ""),
                    question_type=qd.get("type", "UNKNOWN"),
                    source_pages=[p for p, _ in page_texts],
                    number_detected_by="llm",
                ))

    return questions


def _segment_questions(page_texts: List[Tuple[int, str]]) -> List[ExtractedQuestion]:
    """
    Segment text into questions using numbering pattern detection.

    Strategy:
    1. Try each question pattern in order (most specific first)
    2. Use the pattern that produces the most matches
    3. Split text at question boundaries
    4. Handle multi-page stitching
    """
    # Build combined text with page markers
    combined_text = ""
    page_offsets = []  # (start_offset, page_number)

    for page_num, text in page_texts:
        start = len(combined_text)
        combined_text += text + "\n"
        page_offsets.append((start, page_num))

    if not combined_text.strip():
        return []

    # Try each pattern and find the one with the best results
    best_matches = []
    best_pattern_idx = -1

    for pat_idx, pattern in enumerate(QUESTION_PATTERNS):
        matches = list(pattern.finditer(combined_text))
        if len(matches) > len(best_matches):
            best_matches = matches
            best_pattern_idx = pat_idx

    if not best_matches:
        # No question numbers found — treat entire text as one question
        # with positional detection
        all_pages = [p for _, p in page_texts]
        return [ExtractedQuestion(
            question_number=None,
            question_text=combined_text.strip(),
            raw_text=combined_text.strip(),
            source_pages=all_pages,
            number_detected_by="none",
        )]

    # Extract questions between matches
    questions = []
    for i, match in enumerate(best_matches):
        q_number = match.group(1)
        start = match.start()

        # End is the start of the next match, or end of text
        end = best_matches[i + 1].start() if i + 1 < len(best_matches) else len(combined_text)

        q_text = combined_text[start:end].strip()
        raw_text = q_text

        # Remove the question number prefix from the text
        q_text = pattern_strip_number(q_text, QUESTION_PATTERNS[best_pattern_idx])

        # Determine source pages
        source_pages = _get_source_pages(start, end, page_offsets)

        questions.append(ExtractedQuestion(
            question_number=str(q_number),
            question_text=q_text.strip(),
            raw_text=raw_text,
            source_pages=source_pages,
            number_detected_by="regex",
        ))

    return questions


def pattern_strip_number(text: str, pattern: re.Pattern) -> str:
    """Remove the question number prefix from the text."""
    match = pattern.match(text)
    if match:
        return text[match.end():].strip()
    # Fallback: strip common prefixes
    stripped = re.sub(
        r"^(?:Question|Ques\.?|Q\.?)?\s*\d+[.)]\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    return stripped.strip()


def _get_source_pages(start: int, end: int, page_offsets: List[Tuple[int, int]]) -> List[int]:
    """Determine which pages a text span covers."""
    pages = set()
    for i, (offset, page_num) in enumerate(page_offsets):
        next_offset = page_offsets[i + 1][0] if i + 1 < len(page_offsets) else float("inf")
        # Text span overlaps with this page
        if start < next_offset and end > offset:
            pages.add(page_num)
    return sorted(pages)


def _extract_options(text: str) -> List[ExtractedOption]:
    """Extract options (A/B/C/D) from question text."""
    for pattern in OPTION_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) >= 2:  # At least 2 options to be valid
            options = []
            for m in matches:
                label = m.group(1).upper()
                opt_text = m.group(2).strip()
                options.append(ExtractedOption(label=label, text=opt_text))
            return options
    return []


def _classify_question_type(text: str, options: List[ExtractedOption]) -> str:
    """
    Classify a question into a type based on content analysis.

    Priority:
    1. MCQ: has ≥2 labeled options
    2. TRUE_FALSE: contains "True/False" or "T/F" patterns
    3. SHORT: has marks ≤ 2 or short answer indicators
    4. LONG: has marks > 5
    5. UNKNOWN: fallback
    """
    # MCQ: has options
    if len(options) >= 2:
        return "MCQ"

    # True/False
    if TRUE_FALSE_PATTERN.search(text):
        return "TRUE_FALSE"

    # Check marks for SHORT/LONG
    marks_match = MARKS_PATTERN.search(text)
    if marks_match:
        marks = int(marks_match.group(1))
        if marks <= 2:
            return "SHORT"
        elif marks >= 5:
            return "LONG"

    # Short answer indicators
    if SHORT_INDICATORS.search(text):
        return "SHORT"

    # Default to UNKNOWN
    return "UNKNOWN"


def _clean_question_text(text: str, options: List[ExtractedOption]) -> str:
    """Remove option text from the main question body."""
    # Find the start of options and truncate
    for pattern in OPTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return text[:match.start()].strip()
    return text
