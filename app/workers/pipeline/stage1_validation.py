"""
Pipeline Stage 1: File Validation & Normalization.

Runs in the Celery worker (not in the request/response cycle).
Performs:
- Magic-byte re-validation (defense in depth)
- PDF repair attempt via pikepdf
- EXIF rotation fix for images
- Page count guard (MAX_PAGE_COUNT)
- Virus scan hook (adapter call)
- File compression if needed (graduated size policy, Section 7)
"""

import io
import logging
from typing import Tuple

from PIL import Image, ExifTags

from app.adapters.virus_scanner import get_virus_scanner
from app.core.config import get_settings
from app.services.compression_service import CompressionService
from app.services.file_validator import FileValidator, FileValidationError
from app.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)
settings = get_settings()


def run_stage1(document_id: str, storage_path: str, mime_type: str) -> dict:
    """
    Execute Stage 1: Validation & Normalization.

    Args:
        document_id: UUID of the document
        storage_path: Path to the raw file in storage
        mime_type: Detected MIME type from upload

    Returns:
        dict with results:
        {
            "processed_path": str,  # Path to the processed file
            "stored_size_bytes": int,
            "compression_applied": bool,
            "page_count": int or None,
            "pages_to_process": int,
            "pages_skipped": int,
            "is_partial": bool,
            "quality_warnings": list[str],
        }
    """
    storage = get_storage_service()
    file_bytes = storage.read(storage_path)
    original_size = len(file_bytes)
    quality_warnings = []

    # ── Step 1: Magic-byte re-validation (defense in depth) ───────────
    validator = FileValidator()
    try:
        detected_mime = validator.validate_mime_type(file_bytes)
        if detected_mime != mime_type:
            logger.warning(
                f"MIME mismatch in worker: upload={mime_type}, "
                f"worker_detected={detected_mime}. Using worker detection."
            )
            mime_type = detected_mime
    except FileValidationError as e:
        raise ValueError(f"File validation failed in worker: {e.message}")

    # ── Step 2: Virus scan hook ───────────────────────────────────────
    scanner = get_virus_scanner()
    is_clean, scan_message = scanner.scan(file_bytes)
    if not is_clean:
        raise ValueError(f"Virus scan failed: {scan_message}")
    logger.info(f"Virus scan: {scan_message}")

    # ── Step 3: Format-specific validation & normalization ─────────────
    page_count = None
    pages_to_process = None
    pages_skipped = 0
    is_partial = False

    if mime_type == "application/pdf":
        file_bytes, page_count, pages_to_process, pages_skipped, is_partial, pdf_warnings = (
            _validate_pdf(file_bytes)
        )
        quality_warnings.extend(pdf_warnings)
    elif mime_type in ("image/jpeg", "image/png"):
        file_bytes, img_warnings = _validate_image(file_bytes, mime_type)
        quality_warnings.extend(img_warnings)
        page_count = 1
        pages_to_process = 1

    # ── Step 4: Compression if needed (Section 7 graduated policy) ────
    compression_applied = False
    if original_size > settings.max_upload_size_soft_bytes:
        compressor = CompressionService()
        if mime_type == "application/pdf":
            file_bytes, compression_applied = compressor.compress_pdf(file_bytes)
        else:
            file_bytes, compression_applied = compressor.compress_image(file_bytes, mime_type)

        if compression_applied:
            logger.info(
                f"Compression applied: {original_size/(1024*1024):.1f} MB → "
                f"{len(file_bytes)/(1024*1024):.1f} MB "
                f"({(1 - len(file_bytes)/original_size)*100:.1f}% reduction)"
            )

        # If compression couldn't bring it under hard limit, warn but continue
        if len(file_bytes) > settings.max_upload_size_hard_bytes:
            quality_warnings.append("large_file_may_affect_extraction_quality")

    # ── Step 5: Store processed file ──────────────────────────────────
    import uuid
    ext = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }.get(mime_type, "")
    processed_filename = f"{uuid.uuid4()}{ext}"
    processed_path = storage.save_bytes(file_bytes, "processed", processed_filename)

    return {
        "processed_path": processed_path,
        "stored_size_bytes": len(file_bytes),
        "compression_applied": compression_applied,
        "page_count": page_count,
        "pages_to_process": pages_to_process or page_count,
        "pages_skipped": pages_skipped,
        "is_partial": is_partial,
        "quality_warnings": quality_warnings,
    }


def _validate_pdf(file_bytes: bytes) -> Tuple[bytes, int, int, int, bool, list]:
    """
    Validate and normalize a PDF file.

    Returns:
        (file_bytes, page_count, pages_to_process, pages_skipped, is_partial, warnings)
    """
    warnings = []

    # Try to open with pikepdf first (handles repair)
    try:
        import pikepdf
        pdf = pikepdf.open(io.BytesIO(file_bytes))
        page_count = len(pdf.pages)

        # Check for embedded JavaScript (security risk)
        # pikepdf doesn't execute JS, but we log it
        try:
            if "/JS" in str(pdf.Root) or "/JavaScript" in str(pdf.Root):
                warnings.append("pdf_contains_javascript")
                logger.warning(f"PDF contains embedded JavaScript — will not execute")
        except Exception:
            pass

        # Attempt repair by re-saving
        out_buf = io.BytesIO()
        pdf.save(out_buf, compress_streams=True)
        file_bytes = out_buf.getvalue()
        pdf.close()

    except Exception as e:
        logger.warning(f"pikepdf open/repair failed: {e}. Trying PyMuPDF...")
        # Fallback to PyMuPDF
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()
        except Exception as e2:
            raise ValueError(
                f"PDF is corrupt and could not be repaired. "
                f"pikepdf error: {e}, PyMuPDF error: {e2}"
            )

    # Page count guard (Section 7)
    pages_to_process = page_count
    pages_skipped = 0
    is_partial = False

    if page_count > settings.MAX_PAGE_COUNT:
        pages_to_process = settings.MAX_PAGE_COUNT
        pages_skipped = page_count - settings.MAX_PAGE_COUNT
        is_partial = True
        warnings.append(
            f"page_count_exceeded: {page_count} pages, "
            f"processing first {settings.MAX_PAGE_COUNT}"
        )
        logger.warning(
            f"PDF has {page_count} pages, exceeding MAX_PAGE_COUNT={settings.MAX_PAGE_COUNT}. "
            f"Processing first {settings.MAX_PAGE_COUNT} pages."
        )

    return file_bytes, page_count, pages_to_process, pages_skipped, is_partial, warnings


def _validate_image(file_bytes: bytes, mime_type: str) -> Tuple[bytes, list]:
    """
    Validate and normalize an image file.

    Handles EXIF rotation fix (Section 2: image EXIF-rotation fix).
    """
    warnings = []

    try:
        img = Image.open(io.BytesIO(file_bytes))

        # EXIF rotation fix — apply orientation tag and strip EXIF
        try:
            exif = img.getexif()
            orientation_key = None
            for key, val in ExifTags.TAGS.items():
                if val == "Orientation":
                    orientation_key = key
                    break

            if orientation_key and orientation_key in exif:
                orientation = exif[orientation_key]
                rotation_map = {
                    3: 180,
                    6: 270,
                    8: 90,
                }
                if orientation in rotation_map:
                    angle = rotation_map[orientation]
                    img = img.rotate(angle, expand=True)
                    warnings.append(f"exif_rotation_applied: {angle} degrees")
                    logger.info(f"Applied EXIF rotation: {angle}°")
        except Exception as e:
            logger.debug(f"EXIF processing skipped: {e}")

        # Save corrected image
        buf = io.BytesIO()
        fmt = "JPEG" if mime_type == "image/jpeg" else "PNG"
        img.save(buf, format=fmt)
        file_bytes = buf.getvalue()

    except Exception as e:
        warnings.append(f"image_validation_warning: {e}")
        logger.warning(f"Image validation issue: {e}")

    return file_bytes, warnings
