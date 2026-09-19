"""
Storage service — abstract file storage with local filesystem implementation.

Design decisions:
- Never uses client-supplied filenames for storage paths (path traversal prevention).
- Server generates UUID-based paths, client filename stored only as metadata.
- Interface is designed to be swappable to S3/MinIO via adapter pattern.
- Files are never served directly; always streamed through an authenticated endpoint.
"""

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional

from app.core.config import get_settings

settings = get_settings()


class StorageService(ABC):
    """Abstract storage interface — swap implementations for local/S3/MinIO."""

    @abstractmethod
    def save(self, file_data: BinaryIO, bucket: str, filename: Optional[str] = None) -> str:
        """Save file data and return the storage path."""
        ...

    @abstractmethod
    def save_bytes(self, data: bytes, bucket: str, filename: Optional[str] = None) -> str:
        """Save raw bytes and return the storage path."""
        ...

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Read file contents by storage path."""
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists at the given path."""
        ...

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete a file. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def get_full_path(self, path: str) -> str:
        """Get the full filesystem path (for local) or URL (for S3)."""
        ...


class LocalStorageService(StorageService):
    """Local filesystem storage implementation."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or settings.STORAGE_BASE_PATH)
        # Ensure base directories exist
        for subdir in ["raw", "processed", "pages"]:
            (self.base_path / subdir).mkdir(parents=True, exist_ok=True)

    def _generate_path(self, bucket: str, filename: Optional[str] = None) -> str:
        """Generate a UUID-based storage path. Never uses client filenames."""
        if filename is None:
            filename = str(uuid.uuid4())
        return os.path.join(bucket, filename)

    def save(self, file_data: BinaryIO, bucket: str, filename: Optional[str] = None) -> str:
        """Save uploaded file to local storage."""
        rel_path = self._generate_path(bucket, filename)
        full_path = self.base_path / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "wb") as f:
            shutil.copyfileobj(file_data, f)

        return rel_path

    def save_bytes(self, data: bytes, bucket: str, filename: Optional[str] = None) -> str:
        """Save raw bytes to local storage."""
        rel_path = self._generate_path(bucket, filename)
        full_path = self.base_path / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(data)

        return rel_path

    def read(self, path: str) -> bytes:
        """Read file from local storage."""
        full_path = self.base_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return full_path.read_bytes()

    def exists(self, path: str) -> bool:
        """Check if file exists in local storage."""
        return (self.base_path / path).exists()

    def delete(self, path: str) -> bool:
        """Delete file from local storage."""
        full_path = self.base_path / path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def get_full_path(self, path: str) -> str:
        """Get the full filesystem path."""
        return str(self.base_path / path)


def get_storage_service() -> StorageService:
    """Factory function — returns the configured storage backend."""
    if settings.STORAGE_BACKEND == "local":
        return LocalStorageService()
    # Future: add S3StorageService here
    # elif settings.STORAGE_BACKEND == "s3":
    #     return S3StorageService(...)
    else:
        raise ValueError(f"Unknown storage backend: {settings.STORAGE_BACKEND}")
