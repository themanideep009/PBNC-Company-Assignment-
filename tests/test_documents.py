"""Tests for document endpoints: upload, status, list, link."""

import uuid
from io import BytesIO
from unittest.mock import patch

import pytest

from app.models.document import Document, DocumentStatus, DocumentRole


class TestDocumentUpload:
    """Tests for POST /documents."""

    @patch("app.api.documents.RateLimiter")
    def test_upload_pdf_success(self, mock_rl, client, auth_headers, sample_pdf_bytes):
        """Test successful PDF upload returns 202 with document_id."""
        mock_rl.return_value.check_rate_limit.return_value = None

        response = client.post(
            "/documents",
            files={"file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")},
            data={"doc_role": "QUESTION_PAPER"},
            headers=auth_headers,
        )
        assert response.status_code == 202
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "QUEUED"
        assert data["filename"] == "test.pdf"

    @patch("app.api.documents.RateLimiter")
    def test_upload_image_success(self, mock_rl, client, auth_headers, sample_png_bytes):
        """Test successful PNG image upload."""
        mock_rl.return_value.check_rate_limit.return_value = None

        response = client.post(
            "/documents",
            files={"file": ("scan.png", BytesIO(sample_png_bytes), "image/png")},
            headers=auth_headers,
        )
        assert response.status_code == 202

    def test_upload_empty_file(self, client, auth_headers):
        """Test that empty file upload is rejected."""
        response = client.post(
            "/documents",
            files={"file": ("empty.pdf", BytesIO(b""), "application/pdf")},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_upload_requires_auth(self, client, sample_pdf_bytes):
        """Test that upload requires authentication."""
        response = client.post(
            "/documents",
            files={"file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")},
        )
        assert response.status_code == 403


class TestDocumentList:
    """Tests for GET /documents."""

    def test_list_documents_empty(self, client, auth_headers):
        """Test listing with no documents returns empty list."""
        response = client.get("/documents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_documents_pagination(self, client, auth_headers, test_user, db_session):
        """Test pagination parameters work correctly."""
        # Create some documents
        for i in range(5):
            doc = Document(
                owner_id=test_user.id,
                filename=f"doc_{i}.pdf",
                storage_path=f"raw/{uuid.uuid4()}.pdf",
                mime_type="application/pdf",
                original_size_bytes=1000,
                status=DocumentStatus.COMPLETED,
            )
            db_session.add(doc)
        db_session.commit()

        response = client.get(
            "/documents?page=1&page_size=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["total_pages"] == 3


class TestDocumentStatus:
    """Tests for GET /documents/{id}/status."""

    def test_get_status(self, client, auth_headers, test_user, db_session):
        """Test getting document status."""
        doc = Document(
            owner_id=test_user.id,
            filename="test.pdf",
            storage_path="raw/test.pdf",
            mime_type="application/pdf",
            original_size_bytes=5000,
            stored_size_bytes=4000,
            compression_applied=True,
            status=DocumentStatus.COMPLETED,
            page_count=10,
        )
        db_session.add(doc)
        db_session.commit()
        db_session.refresh(doc)

        response = client.get(
            f"/documents/{doc.id}/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["compression_applied"] is True
        assert data["page_count"] == 10

    def test_get_status_not_found(self, client, auth_headers):
        """Test 404 for nonexistent document."""
        response = client.get(
            f"/documents/{uuid.uuid4()}/status",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_status_other_user(self, client, db_session, auth_headers):
        """Test that a user can't see another user's document (returns 404, not 403)."""
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
            owner_id=other_user.id,
            filename="other_user.pdf",
            storage_path="raw/other.pdf",
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
        # Must return 404, NOT 403 — prevents existence leakage
        assert response.status_code == 404
