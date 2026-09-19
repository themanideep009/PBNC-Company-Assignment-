"""
Pipeline Stage 2: Preprocessing.

Converts documents into page images suitable for OCR:
- PDF → page images via PyMuPDF get_pixmap()
- DPI normalization to target DPI
- Deskew via OpenCV (Hough transform based)
- Denoise via OpenCV bilateral filter
- Image dimension capping
"""

import io
import logging
import uuid
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)
settings = get_settings()


def run_stage2(
    document_id: str,
    processed_path: str,
    mime_type: str,
    pages_to_process: int,
) -> List[dict]:
    """
    Execute Stage 2: Preprocessing.

    Converts document into page images and applies image quality improvements.

    Returns:
        List of page dicts:
        [
            {
                "page_number": 1,
                "image_path": "pages/<uuid>.png",
                "has_native_text": bool,
                "rotation_applied": float,
                "quality_flags": dict,
            },
            ...
        ]
    """
    storage = get_storage_service()
    file_bytes = storage.read(processed_path)

    if mime_type == "application/pdf":
        return _process_pdf_pages(file_bytes, document_id, pages_to_process)
    elif mime_type in ("image/jpeg", "image/png"):
        return _process_single_image(file_bytes, document_id, mime_type)
    else:
        raise ValueError(f"Unsupported MIME type for preprocessing: {mime_type}")


def _process_pdf_pages(
    file_bytes: bytes, document_id: str, pages_to_process: int
) -> List[dict]:
    """Convert each PDF page to a preprocessed image."""
    import fitz  # PyMuPDF

    pages = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    try:
        num_pages = min(len(doc), pages_to_process)

        for page_idx in range(num_pages):
            page = doc[page_idx]
            page_number = page_idx + 1

            # Check if page has native text layer
            text = page.get_text("text").strip()
            has_native_text = len(text) > 50  # Threshold for meaningful text

            # Render page to image at target DPI
            target_dpi = settings.TARGET_DPI
            zoom = target_dpi / 72  # Default PDF DPI is 72
            mat = fitz.Matrix(zoom, zoom)

            try:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
            except Exception as e:
                logger.error(f"Failed to render page {page_number}: {e}")
                pages.append({
                    "page_number": page_number,
                    "image_path": None,
                    "has_native_text": has_native_text,
                    "native_text": text if has_native_text else None,
                    "rotation_applied": 0.0,
                    "quality_flags": {"render_failed": str(e)},
                })
                continue

            # Apply preprocessing
            img, rotation, quality_flags = _preprocess_image(img)

            # Save processed page image
            page_filename = f"{document_id}/{uuid.uuid4()}.png"
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_path = get_storage_service().save_bytes(
                buf.getvalue(), "pages", page_filename
            )

            pages.append({
                "page_number": page_number,
                "image_path": image_path,
                "has_native_text": has_native_text,
                "native_text": text if has_native_text else None,
                "rotation_applied": rotation,
                "quality_flags": quality_flags,
            })

            logger.debug(
                f"Processed page {page_number}/{num_pages}: "
                f"native_text={has_native_text}, rotation={rotation}°"
            )

    finally:
        doc.close()

    return pages


def _process_single_image(
    file_bytes: bytes, document_id: str, mime_type: str
) -> List[dict]:
    """Process a single image file as one page."""
    img = Image.open(io.BytesIO(file_bytes))

    # Apply preprocessing
    img, rotation, quality_flags = _preprocess_image(img)

    # Save processed image
    page_filename = f"{document_id}/{uuid.uuid4()}.png"
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_path = get_storage_service().save_bytes(
        buf.getvalue(), "pages", page_filename
    )

    return [{
        "page_number": 1,
        "image_path": image_path,
        "has_native_text": False,
        "native_text": None,
        "rotation_applied": rotation,
        "quality_flags": quality_flags,
    }]


def _preprocess_image(img: Image.Image) -> Tuple[Image.Image, float, dict]:
    """
    Apply image preprocessing pipeline:
    1. Resize if over MAX_IMAGE_DIMENSION_PX
    2. Deskew (if enabled)
    3. Denoise (if enabled)

    Returns:
        (processed_image, rotation_applied, quality_flags)
    """
    quality_flags = {}
    rotation = 0.0

    # Resize if needed
    max_dim = settings.MAX_IMAGE_DIMENSION_PX
    width, height = img.size
    if width > max_dim or height > max_dim:
        if width > height:
            new_w = max_dim
            new_h = int(height * (max_dim / width))
        else:
            new_h = max_dim
            new_w = int(width * (max_dim / height))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        quality_flags["resized"] = f"{width}x{height} → {new_w}x{new_h}"

    # Convert to numpy array for OpenCV processing
    if img.mode != "RGB":
        img = img.convert("RGB")

    img_array = np.array(img)

    # Deskew
    if settings.DESKEW_ENABLED:
        try:
            deskewed, angle = _deskew(img_array)
            if abs(angle) > 0.5:  # Only apply if significant skew detected
                img_array = deskewed
                rotation = angle
                quality_flags["deskew_applied"] = f"{angle:.1f} degrees"
        except Exception as e:
            quality_flags["deskew_failed"] = str(e)
            logger.debug(f"Deskew failed: {e}")

    # Denoise
    if settings.DENOISE_ENABLED:
        try:
            img_array = _denoise(img_array)
            quality_flags["denoised"] = True
        except Exception as e:
            quality_flags["denoise_failed"] = str(e)
            logger.debug(f"Denoise failed: {e}")

    # Convert back to PIL Image
    img = Image.fromarray(img_array)

    return img, rotation, quality_flags


def _deskew(img_array: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Deskew an image using Hough Line Transform.

    Detects text line angles and rotates to correct.
    """
    import cv2

    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Hough Line Transform
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=100,
        minLineLength=100,
        maxLineGap=10,
    )

    if lines is None or len(lines) == 0:
        return img_array, 0.0

    # Calculate the median angle of detected lines
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Only consider near-horizontal lines (±45°)
        if abs(angle) < 45:
            angles.append(angle)

    if not angles:
        return img_array, 0.0

    median_angle = np.median(angles)

    # Only deskew if angle is significant but not too extreme
    if abs(median_angle) < 0.1 or abs(median_angle) > 15:
        return img_array, 0.0

    # Rotate image
    h, w = img_array.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        img_array, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return rotated, median_angle


def _denoise(img_array: np.ndarray) -> np.ndarray:
    """
    Denoise an image using bilateral filter.

    Preserves edges while smoothing noise — better than Gaussian blur
    for document images.
    """
    import cv2

    denoised = cv2.bilateralFilter(img_array, d=9, sigmaColor=75, sigmaSpace=75)
    return denoised
