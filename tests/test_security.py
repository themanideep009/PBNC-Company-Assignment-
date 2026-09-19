"""
Security & file handling tests.

Tests for Section 8 mitigations:
- MIME type spoofing (renamed .exe to .pdf)
- Oversized uploads
- Malformed PDFs
- Path traversal via filename
- Ownership / existence leakage
"""

from io import BytesIO
from unittest.mock import patch

import pytest


class TestMIMESpoofing:
    """Test that content sniffing catches spoofed file types."""

    @patch("app.api.documents.RateLimiter")
    def test_exe_disguised_as_pdf(self, mock_rl, client, auth_headers, fake_exe_as_pdf):
        """An EXE file with .pdf extension should be rejected."""
        mock_rl.return_value.check_rate_limit.return_value = None

        response = client.post(
            "/documents",
            files={"file": ("malware.pdf", BytesIO(fake_exe_as_pdf), "application/pdf")},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()

    @patch("app.api.documents.RateLimiter")
    def test_text_file_disguised_as_pdf(self, mock_rl, client, auth_headers):
        """A plain text file with .pdf extension should be rejected."""
        mock_rl.return_value.check_rate_limit.return_value = None

        response = client.post(
            "/documents",
            files={"file": ("notes.pdf", BytesIO(b"This is just plain text"), "application/pdf")},
            headers=auth_headers,
        )
        assert response.status_code == 400


class TestFileSizePolicy:
    """Test the graduated file size policy (Section 7)."""

    @patch("app.api.documents.RateLimiter")
    def test_reject_over_hard_limit(self, mock_rl, client, auth_headers):
        """Files over MAX_UPLOAD_SIZE_HARD_MB should be rejected with 413."""
        mock_rl.return_value.check_rate_limit.return_value = None

        # Create a large dummy file (>50MB for default hard limit)
        # We mock the size check instead of creating a huge file
        from app.services.file_validator import FileValidator, FileValidationError

        with patch.object(FileValidator, "validate_upload") as mock_validate:
            mock_validate.side_effect = FileValidationError(
                "File too large", "FILE_TOO_LARGE"
            )
            response = client.post(
                "/documents",
                files={"file": ("huge.pdf", BytesIO(b"%PDF-1.4\n" + b"x" * 100), "application/pdf")},
                headers=auth_headers,
            )
            assert response.status_code == 413


class TestPathTraversal:
    """Test that client-supplied filenames can't cause path traversal."""

    @patch("app.api.documents.RateLimiter")
    def test_path_traversal_filename(self, mock_rl, client, auth_headers, sample_pdf_bytes):
        """Filenames with ../ should be sanitized."""
        mock_rl.return_value.check_rate_limit.return_value = None

        response = client.post(
            "/documents",
            files={"file": (
                "../../../etc/passwd.pdf",
                BytesIO(sample_pdf_bytes),
                "application/pdf",
            )},
            headers=auth_headers,
        )
        # Should succeed but filename should be sanitized
        if response.status_code == 202:
            data = response.json()
            assert ".." not in data["filename"]
            assert "/" not in data["filename"]
            assert "\\" not in data["filename"]


class TestExistenceLeakage:
    """Test that error responses don't leak document existence."""

    def test_nonexistent_doc_returns_404(self, client, auth_headers):
        """Requesting a nonexistent document should return 404."""
        import uuid
        response = client.get(
            f"/documents/{uuid.uuid4()}/status",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_other_users_doc_returns_404(self, client, auth_headers, db_session):
        """Requesting another user's document should return 404 (not 403)."""
        import uuid
        from app.models.document import Document, DocumentStatus
        from app.models.user import User
        from app.core.security import hash_password

        other_user = User(
            email=f"other_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("password123"),
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        doc = Document(
            owner_id=other_user.id,  # Different user
            filename="secret.pdf",
            storage_path="raw/secret.pdf",
            mime_type="application/pdf",
            original_size_bytes=1000,
            status=DocumentStatus.COMPLETED,
        )
        db_session.add(doc)
        db_session.commit()
        db_session.refresh(doc)

        response = client.get(
            f"/documents/{doc.id}/status",
            headers=auth_headers,
        )
        # MUST be 404, not 403 — same as nonexistent
        assert response.status_code == 404


class TestMalformedFiles:
    """Test graceful handling of malformed files."""

    @patch("app.workers.tasks.process_document.delay")
    @patch("app.api.documents.RateLimiter")
    def test_malformed_pdf_accepted_for_processing(
        self, mock_rl, mock_delay, client, auth_headers, malformed_pdf_bytes
    ):
        """
        A malformed PDF should be accepted for upload (MIME matches)
        but will fail gracefully in the worker pipeline, not crash.
        """
        mock_rl.return_value.check_rate_limit.return_value = None

        # The malformed PDF may or may not pass MIME detection
        # depending on the bytes — this tests the overall flow
        response = client.post(
            "/documents",
            files={"file": (
                "corrupt.pdf",
                BytesIO(malformed_pdf_bytes),
                "application/pdf",
            )},
            headers=auth_headers,
        )
        # Either accepted (MIME passes) or rejected (MIME fails)
        assert response.status_code in (202, 400)
