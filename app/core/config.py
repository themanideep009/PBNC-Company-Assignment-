"""
Application configuration via pydantic-settings.

All configurable values are loaded from environment variables (or .env file).
No secrets are hardcoded. See .env.example for the full list.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://pragati:pragati_secret@localhost:5432/pragati_bharati"

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT Auth ──────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── File Upload & Size Policy (Section 7) ─────────────────────────────
    MAX_UPLOAD_SIZE_HARD_MB: int = 50
    MAX_UPLOAD_SIZE_SOFT_MB: int = 15
    TARGET_COMPRESSED_SIZE_MB: int = 10
    MAX_PAGE_COUNT: int = 300
    MAX_IMAGE_DIMENSION_PX: int = 4000

    # ── Storage ───────────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    STORAGE_BASE_PATH: str = "/app/storage"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = "pragati-documents"

    # ── OCR ────────────────────────────────────────────────────────────────
    OCR_ENGINE: str = "tesseract"  # "tesseract" or "google_document_ai"
    TESSERACT_CMD: str = ""  # Leave empty to use system default

    # ── Confidence Thresholds ─────────────────────────────────────────────
    CONFIDENCE_AUTO_ACCEPT: float = 0.85
    CONFIDENCE_REVIEW_THRESHOLD: float = 0.50

    # ── Confidence Score Weights (must sum to 1.0) ────────────────────────
    CONFIDENCE_WEIGHT_OCR: float = 0.30
    CONFIDENCE_WEIGHT_NUMBER_DETECTION: float = 0.20
    CONFIDENCE_WEIGHT_OPTION_COMPLETENESS: float = 0.20
    CONFIDENCE_WEIGHT_BOUNDARY_QUALITY: float = 0.15
    CONFIDENCE_WEIGHT_ANSWER_MATCH: float = 0.15

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_UPLOADS_PER_MINUTE: int = 10
    RATE_LIMIT_UPLOADS_BURST: int = 5

    # ── Celery ────────────────────────────────────────────────────────────
    CELERY_TASK_TIMEOUT: int = 600  # 10 minutes per task
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_STALE_JOB_THRESHOLD_MINUTES: int = 30

    # ── Security ──────────────────────────────────────────────────────────
    ALLOWED_MIME_TYPES: str = "application/pdf,image/jpeg,image/png"
    VIRUS_SCAN_ENABLED: bool = False
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = 3310

    # ── Preprocessing ─────────────────────────────────────────────────────
    TARGET_DPI: int = 200
    DESKEW_ENABLED: bool = True
    DENOISE_ENABLED: bool = True

    @property
    def allowed_mime_list(self) -> List[str]:
        """Parse comma-separated MIME types into a list."""
        return [m.strip() for m in self.ALLOWED_MIME_TYPES.split(",")]

    @property
    def max_upload_size_hard_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_HARD_MB * 1024 * 1024

    @property
    def max_upload_size_soft_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_SOFT_MB * 1024 * 1024

    @property
    def target_compressed_size_bytes(self) -> int:
        return self.TARGET_COMPRESSED_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance, loaded once and cached."""
    return Settings()
