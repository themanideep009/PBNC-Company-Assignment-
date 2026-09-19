"""
OCR adapter — abstract interface + Tesseract implementation.

Design: adapter pattern allows swapping OCR engines without changing
the pipeline code. Cloud provider stubs are clearly marked as
integration points.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class OCRWord:
    """Individual word detected by OCR with confidence."""
    text: str
    confidence: float  # 0-100
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class OCRResult:
    """Full OCR result for a page/image."""
    full_text: str
    words: List[OCRWord] = field(default_factory=list)
    average_confidence: float = 0.0
    language: str = "eng"

    @property
    def normalized_confidence(self) -> float:
        """Normalize confidence from 0-100 to 0.0-1.0 scale."""
        return self.average_confidence / 100.0


class OCRAdapter(ABC):
    """Abstract OCR adapter interface."""

    @abstractmethod
    def extract_text(self, image: Image.Image) -> OCRResult:
        """Extract text from an image with per-word confidence."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this OCR engine is available in the environment."""
        ...


class TesseractAdapter(OCRAdapter):
    """
    Tesseract OCR implementation using pytesseract.

    Uses image_to_data for per-word confidence scores.
    Tesseract returns confidence 0-100 per word, with -1 for non-word rows.
    """

    def __init__(self):
        if settings.TESSERACT_CMD:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    def extract_text(self, image: Image.Image) -> OCRResult:
        """
        Extract text with per-word confidence from a PIL Image.

        Uses pytesseract.image_to_data for detailed output including
        bounding boxes and confidence scores per word.
        """
        import pytesseract
        from pytesseract import Output

        try:
            # Get detailed data with confidence scores
            data = pytesseract.image_to_data(
                image, output_type=Output.DICT, lang="eng"
            )

            words = []
            confidences = []

            n_boxes = len(data["text"])
            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = int(data["conf"][i])

                # Skip non-word rows (conf == -1 in Tesseract output)
                if conf == -1 or not text:
                    continue

                words.append(OCRWord(
                    text=text,
                    confidence=float(conf),
                    x=data["left"][i],
                    y=data["top"][i],
                    width=data["width"][i],
                    height=data["height"][i],
                ))
                confidences.append(conf)

            # Also get the full text (preserves line structure better)
            full_text = pytesseract.image_to_string(image, lang="eng")

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                full_text=full_text.strip(),
                words=words,
                average_confidence=avg_confidence,
            )

        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return OCRResult(full_text="", average_confidence=0.0)

    def is_available(self) -> bool:
        """Check if Tesseract is installed and accessible."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False


class CloudOCRStub(OCRAdapter):
    """
    Stub for cloud OCR providers (Google Document AI, AWS Textract, Azure DI).

    INTEGRATION POINT: Replace this with actual cloud provider SDK calls.
    All credentials must be loaded from environment variables.
    Request/response logging must redact document content (PII/content protection).

    To wire in production:
    1. Install the provider's SDK (e.g., google-cloud-documentai)
    2. Set credentials via environment variables
    3. Implement extract_text using the provider's API
    4. Ensure calls are logged with content redaction
    """

    def extract_text(self, image: Image.Image) -> OCRResult:
        """Stub — not implemented. Use TesseractAdapter or implement a cloud provider."""
        raise NotImplementedError(
            "Cloud OCR is a stub. Set OCR_ENGINE=tesseract or implement "
            "a cloud provider adapter (see CloudOCRStub docstring)."
        )

    def is_available(self) -> bool:
        return False


def get_ocr_adapter() -> OCRAdapter:
    """Factory — returns the configured OCR adapter."""
    if settings.OCR_ENGINE == "tesseract":
        adapter = TesseractAdapter()
        if not adapter.is_available():
            logger.warning("Tesseract not found. OCR will fail for scanned documents.")
        return adapter
    elif settings.OCR_ENGINE in ("google_document_ai", "aws_textract", "azure_di"):
        logger.warning(
            f"Cloud OCR ({settings.OCR_ENGINE}) is a stub. "
            "Falling back to Tesseract."
        )
        return TesseractAdapter()
    else:
        raise ValueError(f"Unknown OCR engine: {settings.OCR_ENGINE}")
