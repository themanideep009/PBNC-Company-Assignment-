"""
FastAPI application factory.

Creates the FastAPI app with all routers, middleware, and startup events.
OpenAPI/Swagger available at /docs (auto-generated).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.celery_app import celery_app
from app.core.config import get_settings

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    logger.info("Pragati Bharati API starting up...")
    logger.info(f"Storage backend: {settings.STORAGE_BACKEND}")
    logger.info(f"OCR engine: {settings.OCR_ENGINE}")
    logger.info(f"Max upload size (hard): {settings.MAX_UPLOAD_SIZE_HARD_MB} MB")
    logger.info(f"Max upload size (soft): {settings.MAX_UPLOAD_SIZE_SOFT_MB} MB")
    yield
    logger.info("Pragati Bharati API shutting down...")


app = FastAPI(
    title="Pragati Bharati — Document Intelligence API",
    description=(
        "Document Processing & Question Extraction Service for ed-tech. "
        "Upload exam papers and question banks (PDF/image), extract structured "
        "questions with answer-key association, confidence scoring, and review queue."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routes (support both root and /api/v1 prefix)
app.include_router(api_router)
app.include_router(api_router, prefix="/api/v1")


# Global exception handler for unhandled errors — never leak internals
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for unhandled exceptions.
    Log the real error server-side, return a generic error to the client.
    This prevents internal error details from leaking (Section 8).
    """
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )
