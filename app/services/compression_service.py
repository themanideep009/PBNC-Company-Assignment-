"""
Compression service — graduated file size policy implementation (Section 7).

This runs in the Celery WORKER, not in the request/response cycle.
The upload endpoint only does cheap sync checks (MIME sniff, hard-limit size).
Compression is Stage 1 of the async pipeline.

Behavior:
1. PDFs: downsample embedded images, strip metadata, re-save with compression
2. Images: resize to MAX_IMAGE_DIMENSION_PX, progressive JPEG quality stepping
3. Records original_size_bytes and stored_size_bytes for auditability
"""

import io
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CompressionService:
    """Handles file compression for the graduated size policy."""

    def compress_pdf_ghostscript(
        self, input_path: str, output_path: str, quality: str = "/ebook"
    ) -> bool:
        """
        Compress a PDF using Ghostscript.

        Quality presets (from most to least compressed):
        - /screen: 72 DPI, smallest files
        - /ebook: 150 DPI, good for on-screen viewing
        - /printer: 300 DPI, high quality
        - /prepress: 300 DPI, highest quality

        We start with /ebook and step down to /screen if needed.
        """
        try:
            cmd = [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={quality}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-dAutoRotatePages=/None",  # Preserve original rotation
                f"-sOutputFile={output_path}",
                input_path,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for compression
            )
            if result.returncode != 0:
                logger.error(f"Ghostscript compression failed: {result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("Ghostscript compression timed out")
            return False
        except FileNotFoundError:
            logger.error("Ghostscript not found — install ghostscript package")
            return False

    def compress_pdf(self, file_bytes: bytes) -> Tuple[bytes, bool]:
        """
        Compress a PDF file using Ghostscript with progressive quality stepping.

        Tries /ebook first, then /screen if still over target size.
        Falls back to pikepdf if Ghostscript is unavailable.

        Returns:
            (compressed_bytes, compression_applied)
        """
        target_size = settings.target_compressed_size_bytes
        original_size = len(file_bytes)

        if original_size <= target_size:
            return file_bytes, False

        # Try Ghostscript compression with progressive quality stepping
        qualities = ["/ebook", "/screen"]

        for quality in qualities:
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
                    tmp_in.write(file_bytes)
                    tmp_in_path = tmp_in.name

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out:
                    tmp_out_path = tmp_out.name

                success = self.compress_pdf_ghostscript(tmp_in_path, tmp_out_path, quality)

                if success:
                    compressed = Path(tmp_out_path).read_bytes()
                    compressed_size = len(compressed)

                    logger.info(
                        f"PDF compression ({quality}): "
                        f"{original_size / (1024*1024):.1f} MB → "
                        f"{compressed_size / (1024*1024):.1f} MB "
                        f"({(1 - compressed_size/original_size)*100:.1f}% reduction)"
                    )

                    if compressed_size <= target_size:
                        return compressed, True

                    # Continue to next quality level if still over target
                    file_bytes = compressed  # Use compressed version as next input

            except Exception as e:
                logger.error(f"PDF compression error with {quality}: {e}")
            finally:
                # Clean up temp files
                for p in [tmp_in_path, tmp_out_path]:
                    try:
                        Path(p).unlink(missing_ok=True)
                    except Exception:
                        pass

        # Fallback: try pikepdf for basic cleanup
        try:
            import pikepdf
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            pdf = pikepdf.open(tmp_path)
            out_path = tmp_path + "_compressed.pdf"
            pdf.save(
                out_path,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
            pdf.close()
            compressed = Path(out_path).read_bytes()
            Path(tmp_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

            if len(compressed) < original_size:
                return compressed, True

        except Exception as e:
            logger.error(f"pikepdf compression fallback error: {e}")

        # If nothing worked, return the best we have
        return file_bytes, len(file_bytes) < original_size

    def compress_image(self, file_bytes: bytes, mime_type: str) -> Tuple[bytes, bool]:
        """
        Compress an image file:
        1. Resize to MAX_IMAGE_DIMENSION_PX on the long edge
        2. For JPEG: progressive quality stepping (85 → 70 → 55 → 40)
        3. For PNG with transparency: preserve as PNG
        4. For PNG without transparency: convert to JPEG

        Returns:
            (compressed_bytes, compression_applied)
        """
        target_size = settings.target_compressed_size_bytes
        original_size = len(file_bytes)

        if original_size <= target_size:
            return file_bytes, False

        try:
            img = Image.open(io.BytesIO(file_bytes))
            max_dim = settings.MAX_IMAGE_DIMENSION_PX

            # Resize if needed (maintain aspect ratio)
            width, height = img.size
            if width > max_dim or height > max_dim:
                if width > height:
                    new_width = max_dim
                    new_height = int(height * (max_dim / width))
                else:
                    new_height = max_dim
                    new_width = int(width * (max_dim / height))
                img = img.resize((new_width, new_height), Image.LANCZOS)
                logger.info(f"Image resized: {width}x{height} → {new_width}x{new_height}")

            # Check for transparency (preserve PNG if transparent)
            has_transparency = (
                img.mode == "RGBA" and
                mime_type == "image/png"
            )

            if has_transparency:
                # Compress PNG
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                return buf.getvalue(), True

            # Convert to RGB for JPEG output
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Progressive JPEG quality stepping
            for quality in [85, 70, 55, 40]:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                compressed = buf.getvalue()

                logger.info(
                    f"Image compression (quality={quality}): "
                    f"{original_size / (1024*1024):.1f} MB → "
                    f"{len(compressed) / (1024*1024):.1f} MB"
                )

                if len(compressed) <= target_size:
                    return compressed, True

            # Return the most compressed version even if over target
            return compressed, True

        except Exception as e:
            logger.error(f"Image compression error: {e}")
            return file_bytes, False
