"""
File validation service — MIME type sniffing and security checks.

Security mitigations (Section 8):
- Content sniffs using python-magic (libmagic), NOT file extension or Content-Type header.
- Rejects files whose MIME doesn't match the allowlist regardless of extension.
- Pillow MAX_IMAGE_PIXELS guard against decompression bombs.
- Never trusts client-supplied MIME type.
"""

import logging
from typing import Tuple

import magic
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Guard against decompression bomb images (Section 8: zip-bomb-style PDFs)
# Default is ~178 million pixels; we cap at 200 million
Image.MAX_IMAGE_PIXELS = 200_000_000


class FileValidationError(Exception):
    """Raised when a file fails validation."""

    def __init__(self, message: str, error_code: str = "INVALID_FILE"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class FileValidator:
    """Validates uploaded files for type safety and size constraints."""

    def __init__(self):
        self.allowed_mimes = settings.allowed_mime_list
        self.hard_limit = settings.max_upload_size_hard_bytes
        self.soft_limit = settings.max_upload_size_soft_bytes

    def sniff_mime_type(self, file_bytes: bytes) -> str:
        """
        Detect MIME type from file content using libmagic.

        This is the ONLY trusted MIME detection method. We never trust:
        - Client-supplied Content-Type header
        - File extension
        Both can be trivially spoofed.
        """
        detected = magic.from_buffer(file_bytes[:8192], mime=True)
        logger.debug(f"Content-sniffed MIME type: {detected}")
        return detected

    def validate_mime_type(self, file_bytes: bytes) -> str:
        """
        Validate that the file's actual content matches an allowed MIME type.

        Returns the detected MIME type on success.
        Raises FileValidationError if the MIME is not allowed.
        """
        detected_mime = self.sniff_mime_type(file_bytes)

        if detected_mime not in self.allowed_mimes:
            logger.warning(
                f"Rejected file with MIME type: {detected_mime}. "
                f"Allowed: {self.allowed_mimes}"
            )
            raise FileValidationError(
                message=(
                    f"File type '{detected_mime}' is not allowed. "
                    f"Accepted types: {', '.join(self.allowed_mimes)}"
                ),
                error_code="INVALID_MIME_TYPE",
            )

        return detected_mime

    def validate_size(self, size_bytes: int) -> Tuple[bool, bool]:
        """
        Check file size against the graduated policy (Section 7).

        Returns:
            (accepted, needs_compression):
            - (True, False): under soft limit, no compression needed
            - (True, True): between soft and hard limit, needs compression
            - Raises FileValidationError if over hard limit
        """
        if size_bytes > self.hard_limit:
            raise FileValidationError(
                message=(
                    f"File size ({size_bytes / (1024*1024):.1f} MB) exceeds the "
                    f"maximum limit of {settings.MAX_UPLOAD_SIZE_HARD_MB} MB. "
                    f"Please compress the file before uploading."
                ),
                error_code="FILE_TOO_LARGE",
            )

        needs_compression = size_bytes > self.soft_limit
        return True, needs_compression

    def validate_image_dimensions(self, image: Image.Image) -> None:
        """
        Validate image dimensions against the configured maximum.

        Raises FileValidationError if either dimension exceeds the limit.
        Note: this is a WARNING, not a hard rejection — images will be
        resized in the compression pipeline. This check is for logging.
        """
        width, height = image.size
        max_dim = settings.MAX_IMAGE_DIMENSION_PX
        if width > max_dim or height > max_dim:
            logger.info(
                f"Image dimensions ({width}x{height}) exceed max "
                f"({max_dim}px). Will be resized during preprocessing."
            )

    def validate_upload(self, file_bytes: bytes, filename: str) -> Tuple[str, bool]:
        """
        Full upload validation: MIME type + size check.

        Args:
            file_bytes: Raw file content
            filename: Client-supplied filename (for logging only, never used for storage)

        Returns:
            (detected_mime_type, needs_compression)

        Raises:
            FileValidationError: if file fails validation
        """
        # Step 1: MIME type check (content sniffing, not extension)
        detected_mime = self.validate_mime_type(file_bytes)

        # Step 2: Size check (graduated policy)
        _, needs_compression = self.validate_size(len(file_bytes))

        logger.info(
            f"File validated: filename='{filename}', "
            f"mime={detected_mime}, size={len(file_bytes)}, "
            f"needs_compression={needs_compression}"
        )

        return detected_mime, needs_compression
