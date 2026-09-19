"""
Pipeline Stage 6: Confidence Scoring & Review Flag Assignment.

Computes a composite confidence score from measurable signals:
- OCR engine's per-word confidence
- Question number detection method (regex vs. positional)
- Option completeness (found options / expected options)
- Boundary quality (clean page breaks vs. mid-sentence)
- Answer match quality

Thresholds are loaded from config (not hardcoded):
- >= CONFIDENCE_AUTO_ACCEPT → auto-accept
- CONFIDENCE_REVIEW_THRESHOLD to CONFIDENCE_AUTO_ACCEPT → flag for review
- < CONFIDENCE_REVIEW_THRESHOLD → mark UNRELIABLE

Every review-flagged item retains: page image reference, raw OCR text,
and specific reason string (not just a boolean).
"""

import logging
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.workers.pipeline.stage4_segmentation import ExtractedQuestion
from app.workers.pipeline.stage5_answer_key import ExtractedAnswer

logger = logging.getLogger(__name__)
settings = get_settings()


def run_stage6(
    questions: List[ExtractedQuestion],
    answers: Dict[str, ExtractedAnswer],
    page_data_list: List[dict],
) -> List[dict]:
    """
    Execute Stage 6: Confidence Scoring & Review Assignment.

    Args:
        questions: Extracted questions from Stage 4
        answers: Matched answers from Stage 5
        page_data_list: Page data with OCR confidence from Stage 3

    Returns:
        List of scored question dicts ready for database insertion:
        [
            {
                "question": ExtractedQuestion,
                "answer": ExtractedAnswer or None,
                "confidence": float,
                "review_required": bool,
                "review_reason": str or None,
                "review_severity": str,
            },
            ...
        ]
    """
    # Build OCR confidence lookup by page
    page_ocr_confidence = {}
    for page_data in page_data_list:
        page_num = page_data["page_number"]
        page_ocr_confidence[page_num] = page_data.get("ocr_confidence", 0.0)

    results = []

    for question in questions:
        answer = answers.get(question.question_number) if question.question_number else None

        # Compute composite confidence
        confidence, reasons = _compute_confidence(
            question, answer, page_ocr_confidence
        )

        # Determine review status based on thresholds
        review_required = confidence < settings.CONFIDENCE_AUTO_ACCEPT
        review_reason = None
        review_severity = "MEDIUM"

        if confidence < settings.CONFIDENCE_REVIEW_THRESHOLD:
            review_severity = "HIGH"
            review_reason = f"Low confidence ({confidence:.2f}): " + "; ".join(reasons)
        elif confidence < settings.CONFIDENCE_AUTO_ACCEPT:
            review_severity = "MEDIUM"
            review_reason = f"Moderate confidence ({confidence:.2f}): " + "; ".join(reasons)

        results.append({
            "question": question,
            "answer": answer,
            "confidence": round(confidence, 4),
            "review_required": review_required,
            "review_reason": review_reason,
            "review_severity": review_severity,
        })

    # Log summary
    auto_accepted = sum(1 for r in results if not r["review_required"])
    review_needed = sum(1 for r in results if r["review_required"])
    logger.info(
        f"Confidence scoring: {auto_accepted} auto-accepted, "
        f"{review_needed} flagged for review out of {len(results)} questions"
    )

    return results


def _compute_confidence(
    question: ExtractedQuestion,
    answer: Optional[ExtractedAnswer],
    page_ocr_confidence: Dict[int, float],
) -> tuple:
    """
    Compute composite confidence score from individual signals.

    Formula:
        confidence = sum(weight_i * signal_i)

    Signals and weights are loaded from config.

    Returns:
        (confidence_score, list_of_reason_strings)
    """
    signals = {}
    reasons = []

    # ── Signal 1: OCR Confidence ──────────────────────────────────────
    if question.source_pages:
        page_confidences = [
            page_ocr_confidence.get(p, 0.0) for p in question.source_pages
        ]
        avg_ocr = sum(page_confidences) / len(page_confidences) if page_confidences else 0.0
    else:
        avg_ocr = 0.5  # No page info, assume medium

    signals["ocr"] = avg_ocr
    if avg_ocr < 0.6:
        reasons.append(f"low OCR confidence ({avg_ocr:.2f})")

    # ── Signal 2: Number Detection Quality ────────────────────────────
    if question.number_detected_by == "regex":
        signals["number_detection"] = 1.0
    elif question.number_detected_by == "positional":
        signals["number_detection"] = 0.5
        reasons.append("question number inferred by position, not regex")
    elif question.number_detected_by == "llm":
        signals["number_detection"] = 0.7
    else:
        signals["number_detection"] = 0.3
        reasons.append("question number not detected")

    # ── Signal 3: Option Completeness ─────────────────────────────────
    if question.question_type == "MCQ":
        expected_options = 4  # Standard A/B/C/D
        found_options = len(question.options)
        signals["option_completeness"] = min(found_options / expected_options, 1.0)
        if found_options < expected_options:
            reasons.append(
                f"incomplete options ({found_options}/{expected_options})"
            )
    elif question.question_type == "TRUE_FALSE":
        signals["option_completeness"] = 1.0 if len(question.options) >= 2 else 0.8
    else:
        signals["option_completeness"] = 1.0  # N/A for non-MCQ

    # ── Signal 4: Boundary Quality ────────────────────────────────────
    text = question.question_text.strip()
    if text:
        # Check if text ends cleanly (punctuation or option) vs. mid-sentence
        ends_cleanly = (
            text[-1] in ".?!:)" or
            len(question.options) > 0 or
            text[-1] == "]"
        )
        # Check if text starts cleanly (capitalized word, not mid-sentence)
        starts_cleanly = (
            text[0].isupper() or
            text[0].isdigit() or
            text[0] in "([\"'"
        )
        boundary_score = 0.5
        if ends_cleanly:
            boundary_score += 0.25
        if starts_cleanly:
            boundary_score += 0.25
        signals["boundary_quality"] = boundary_score

        if not ends_cleanly:
            reasons.append("question text may be truncated (no clean ending)")
    else:
        signals["boundary_quality"] = 0.0
        reasons.append("empty question text")

    # ── Signal 5: Answer Match Quality ────────────────────────────────
    if answer:
        if answer.match_type == "exact":
            signals["answer_match"] = answer.match_confidence
        elif answer.match_type == "fuzzy":
            signals["answer_match"] = answer.match_confidence * 0.8
            reasons.append("answer matched by fuzzy/numeric matching")
        elif answer.match_type == "positional":
            signals["answer_match"] = 0.5
            reasons.append("answer matched by position only")
        else:
            signals["answer_match"] = 0.3
    else:
        signals["answer_match"] = 0.5  # Neutral — no answer isn't necessarily bad
        # Only flag if this is a question that should have an answer
        if question.question_type in ("MCQ", "TRUE_FALSE"):
            reasons.append("no answer found for MCQ/T-F question")
            signals["answer_match"] = 0.4

    # ── Compute Weighted Sum ──────────────────────────────────────────
    confidence = (
        settings.CONFIDENCE_WEIGHT_OCR * signals["ocr"]
        + settings.CONFIDENCE_WEIGHT_NUMBER_DETECTION * signals["number_detection"]
        + settings.CONFIDENCE_WEIGHT_OPTION_COMPLETENESS * signals["option_completeness"]
        + settings.CONFIDENCE_WEIGHT_BOUNDARY_QUALITY * signals["boundary_quality"]
        + settings.CONFIDENCE_WEIGHT_ANSWER_MATCH * signals["answer_match"]
    )

    # Clamp to [0, 1]
    confidence = max(0.0, min(1.0, confidence))

    return confidence, reasons
