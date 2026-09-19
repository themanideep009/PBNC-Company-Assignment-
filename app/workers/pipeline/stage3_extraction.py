"""
Pipeline Stage 3: Text/Layout Extraction.

Two paths:
1. Digital PDF with native text layer → extract using PyMuPDF get_text("blocks")
2. Scanned/image document → OCR using Tesseract (via adapter)

Outputs per-page text with confidence scores stored in the pages table.
"""

import io
import logging
from typing import List, Optional

from PIL import Image

from app.adapters.ocr_adapter import get_ocr_adapter, OCRResult
from app.core.config import get_settings
from app.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)
settings = get_settings()


def run_stage3(page_data_list: List[dict]) -> List[dict]:
    """
    Execute Stage 3: Text Extraction.

    For each page, either use native text (if available from digital PDF)
    or run OCR on the page image.

    Args:
        page_data_list: List of page dicts from Stage 2, each containing:
            - page_number
            - image_path
            - has_native_text
            - native_text (if has_native_text)

    Returns:
        Updated page_data_list with added fields:
            - ocr_text: str
            - ocr_confidence: float (0.0-1.0)
            - extraction_method: "native" or "ocr"
    """
    ocr = get_ocr_adapter()
    storage = get_storage_service()

    for page_data in page_data_list:
        page_num = page_data["page_number"]

        if page_data.get("has_native_text") and page_data.get("native_text"):
            # Digital PDF — use native text layer
            page_data["ocr_text"] = page_data["native_text"]
            page_data["ocr_confidence"] = 1.0  # Native text is 100% confident
            page_data["extraction_method"] = "native"
            logger.debug(
                f"Page {page_num}: native text extracted "
                f"({len(page_data['native_text'])} chars)"
            )
        else:
            # Scanned/image — run OCR
            if page_data.get("image_path"):
                try:
                    image_bytes = storage.read(page_data["image_path"])
                    img = Image.open(io.BytesIO(image_bytes))

                    result: OCRResult = ocr.extract_text(img)

                    page_data["ocr_text"] = result.full_text
                    page_data["ocr_confidence"] = result.normalized_confidence
                    page_data["extraction_method"] = "ocr"

                    logger.debug(
                        f"Page {page_num}: OCR extracted "
                        f"({len(result.full_text)} chars, "
                        f"confidence={result.normalized_confidence:.2f})"
                    )

                except Exception as e:
                    logger.error(f"OCR failed for page {page_num}: {e}")
                    page_data["ocr_text"] = ""
                    page_data["ocr_confidence"] = 0.0
                    page_data["extraction_method"] = "ocr_failed"
                    page_data.setdefault("quality_flags", {})["ocr_failed"] = str(e)
            else:
                # No image available (render failed in Stage 2)
                page_data["ocr_text"] = ""
                page_data["ocr_confidence"] = 0.0
                page_data["extraction_method"] = "unavailable"

    return page_data_list


def extract_text_from_pdf_native(file_bytes: bytes) -> List[dict]:
    """
    Extract text from a PDF using PyMuPDF's native text extraction.

    Uses get_text("blocks") for block-level extraction with bounding boxes.
    This preserves the spatial layout better than plain text extraction.

    Returns:
        List of dicts per page with extracted text blocks.
    """
    import fitz

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            blocks = page.get_text("blocks")

            # Sort blocks by vertical position (reading order)
            blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

            text_parts = []
            for block in blocks:
                # block = (x0, y0, x1, y1, text, block_no, block_type)
                if block[6] == 0:  # type 0 = text block
                    text_parts.append(block[4].strip())

            full_text = "\n".join(text_parts)

            pages.append({
                "page_number": page_idx + 1,
                "text": full_text,
                "block_count": len(blocks),
            })
    finally:
        doc.close()

    return pages
