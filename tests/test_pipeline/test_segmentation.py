"""
Unit tests for Stage 4: Question Segmentation.

Tests regex patterns for question number detection, option extraction,
and question type classification without needing a database or OCR.
"""

import pytest

from app.workers.pipeline.stage4_segmentation import (
    ExtractedQuestion,
    _segment_questions,
    _extract_options,
    _classify_question_type,
    run_stage4,
)


class TestQuestionNumberDetection:
    """Test that various question number formats are detected."""

    def test_dot_format(self):
        """Test '1. Question text' format."""
        pages = [(1, "1. What is Python?\n2. What is Java?\n3. What is C++?")]
        questions = _segment_questions(pages)
        assert len(questions) == 3
        assert questions[0].question_number == "1"
        assert questions[1].question_number == "2"
        assert questions[2].question_number == "3"

    def test_paren_format(self):
        """Test '1) Question text' format."""
        pages = [(1, "1) What is Python?\n2) What is Java?")]
        questions = _segment_questions(pages)
        assert len(questions) == 2

    def test_q_dot_format(self):
        """Test 'Q.1 Question text' format."""
        pages = [(1, "Q.1 What is Python?\nQ.2 What is Java?")]
        questions = _segment_questions(pages)
        assert len(questions) == 2
        assert questions[0].question_number == "1"

    def test_question_word_format(self):
        """Test 'Question 1 ...' format."""
        pages = [(1, "Question 1 What is Python?\nQuestion 2 What is Java?")]
        questions = _segment_questions(pages)
        assert len(questions) == 2

    def test_multi_page_stitching(self):
        """Test that questions spanning multiple pages are stitched."""
        pages = [
            (1, "1. What is the capital of France?"),
            (2, "2. What is the capital of Germany?\n3. Name the largest ocean."),
        ]
        questions = _segment_questions(pages)
        assert len(questions) == 3
        # Question 2 starts on page 2
        assert 2 in questions[1].source_pages


class TestOptionExtraction:
    """Test MCQ option detection."""

    def test_letter_paren_options(self):
        """Test '(A) text' format."""
        text = "(A) Red\n(B) Blue\n(C) Green\n(D) Yellow"
        options = _extract_options(text)
        assert len(options) == 4
        assert options[0].label == "A"
        assert options[0].text == "Red"

    def test_letter_dot_options(self):
        """Test 'A. text' format."""
        text = "A. Red\nB. Blue\nC. Green\nD. Yellow"
        options = _extract_options(text)
        assert len(options) == 4

    def test_letter_paren_close_options(self):
        """Test 'A) text' format."""
        text = "A) Red\nB) Blue\nC) Green"
        options = _extract_options(text)
        assert len(options) == 3

    def test_no_options(self):
        """Test text without options returns empty list."""
        text = "Define photosynthesis in your own words."
        options = _extract_options(text)
        assert len(options) == 0


class TestQuestionTypeClassification:
    """Test question type classification logic."""

    def test_mcq_detection(self):
        """Questions with ≥2 options should be MCQ."""
        from app.workers.pipeline.stage4_segmentation import ExtractedOption
        options = [
            ExtractedOption(label="A", text="Red"),
            ExtractedOption(label="B", text="Blue"),
            ExtractedOption(label="C", text="Green"),
        ]
        result = _classify_question_type("Which color is primary?", options)
        assert result == "MCQ"

    def test_true_false_detection(self):
        """Questions with 'True or False' should be TRUE_FALSE."""
        result = _classify_question_type(
            "State True or False: The earth is flat.", []
        )
        assert result == "TRUE_FALSE"

    def test_short_answer_detection(self):
        """Questions with 'Define' should be SHORT."""
        result = _classify_question_type("Define osmosis. [2 marks]", [])
        assert result == "SHORT"

    def test_long_answer_detection(self):
        """Questions with high marks should be LONG."""
        result = _classify_question_type(
            "Explain the process of photosynthesis in detail. [10 marks]", []
        )
        assert result == "LONG"

    def test_unknown_fallback(self):
        """Questions that don't match any pattern should be UNKNOWN."""
        result = _classify_question_type("Discuss the following.", [])
        assert result == "UNKNOWN"


class TestFullSegmentation:
    """Integration tests for the full Stage 4 pipeline."""

    def test_mixed_question_types(self):
        """Test segmentation of a document with mixed question types."""
        page_data = [{
            "page_number": 1,
            "ocr_text": (
                "1. Which of the following is a prime number?\n"
                "(A) 4\n(B) 7\n(C) 9\n(D) 12\n"
                "2. State True or False: Water boils at 100°C.\n"
                "3. Define photosynthesis. [2 marks]\n"
                "4. Explain the water cycle in detail. [10 marks]"
            ),
        }]
        questions = run_stage4(page_data)
        assert len(questions) >= 3

        # Check types
        types = {q.question_type for q in questions}
        assert "MCQ" in types or "TRUE_FALSE" in types  # At least some detected
