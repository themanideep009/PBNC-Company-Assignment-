"""
LLM adapter — stub interface for LLM-assisted question segmentation.

INTEGRATION POINT: Provides an adapter pattern for wiring any LLM provider
(OpenAI, Google Gemini, Anthropic, local models) for ambiguous segmentation.

Current implementation: STUB ONLY.
The segmentation pipeline (stage4) uses regex + layout heuristics by default.
This adapter is called only when heuristics produce low-confidence results,
and in the stub implementation it simply returns None (no LLM assist).

Production wiring:
1. Install the provider SDK
2. Set LLM credentials via environment variables
3. Implement the segment_text method
4. Ensure all API calls are logged WITH CONTENT REDACTION (PII protection)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMSegmentResult:
    """Result from LLM-assisted segmentation."""
    questions: List[dict]  # List of {question_number, question_text, options, type}
    confidence: float


class LLMAdapter(ABC):
    """Abstract LLM adapter interface for segmentation assistance."""

    @abstractmethod
    def segment_text(self, raw_text: str, context: str = "") -> Optional[LLMSegmentResult]:
        """
        Ask an LLM to help segment ambiguous text into questions.

        Args:
            raw_text: The extracted text that needs segmentation.
            context: Additional context (e.g., "exam paper, math subject").

        Returns:
            LLMSegmentResult or None if segmentation failed/unavailable.
        """
        ...


class LLMAdapterStub(LLMAdapter):
    """
    Stub LLM adapter — returns None (no LLM assist).

    The pipeline falls back to regex + heuristic segmentation.
    This is the default when no LLM is configured.
    """

    def segment_text(self, raw_text: str, context: str = "") -> Optional[LLMSegmentResult]:
        logger.debug(
            "LLM segmentation is disabled (stub). "
            "Using regex + heuristic segmentation only."
        )
        return None


def get_llm_adapter() -> LLMAdapter:
    """Factory — returns the configured LLM adapter (stub by default)."""
    return LLMAdapterStub()
