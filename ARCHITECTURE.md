# ARCHITECTURE.md — Pragati Bharati Document Intelligence Service

## 1. System Architecture

```
┌──────────┐    JWT Auth     ┌───────────────────────────────────────────┐
│  Client  │ ──────────────► │         FastAPI (API Layer)               │
│ (Browser │                 │  /auth, /documents, /questions,          │
│  or App) │                 │  /review-queue, /healthz, /docs          │
└──────────┘                 └────────────────┬──────────────────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         │                    │                    │
                         ▼                    ▼                    ▼
                  ┌──────────┐       ┌──────────────┐    ┌─────────────┐
                  │ Postgres │       │    Redis      │    │   Object    │
                  │  (Data)  │       │ (Queue/Cache) │    │  Storage    │
                  └──────────┘       └──────┬───────┘    │ (Local/S3)  │
                                            │            └──────┬──────┘
                                            ▼                   │
                              ┌──────────────────────────┐      │
                              │   Celery Worker Pool     │◄─────┘
                              │  (Horizontally Scalable) │
                              │                          │
                              │  Stage 1: Validation     │
                              │  Stage 2: Preprocessing  │
                              │  Stage 3: Extraction     │
                              │  Stage 4: Segmentation   │
                              │  Stage 5: Answer Key     │
                              │  Stage 6: Confidence     │
                              └──────────────────────────┘
```

## 2. Technology Choices

### Task Queue: Celery + Redis

**Choice:** Celery with Redis as broker and result backend.

**Why Celery over alternatives:**
- **vs. RQ**: RQ is simpler but lacks built-in retry with backoff, task timeouts, periodic tasks (beat), and monitoring (Flower). These are critical for a production document processing pipeline where tasks can hang or fail.
- **vs. Arq**: Arq is async-native but has a smaller ecosystem, fewer production deployments at scale, and less documentation. Celery's maturity (10+ years) and extensive plugin ecosystem make it the safer choice.
- **Redis as broker**: Operational simplicity — one fewer service to manage compared to RabbitMQ. Redis also serves as the rate-limiting backend and job status cache, reducing infrastructure complexity.

### OCR: Tesseract (Primary) + Adapter Interface

**Choice:** Tesseract via pytesseract as the primary OCR engine.

**Why:**
- Free, open-source, no API key or cloud dependency
- Provides per-word confidence scores via `image_to_data` — essential for our composite confidence scoring
- Good enough for printed text documents (our primary use case)
- Cloud providers (Google Document AI, AWS Textract) can be swapped in via the `OCRAdapter` interface without changing pipeline code

**Adapter pattern:** `app/adapters/ocr_adapter.py` defines an abstract `OCRAdapter` class. `TesseractAdapter` is the concrete implementation. `CloudOCRStub` is a documented integration point for cloud providers. All credentials are environment-based.

### PDF Processing: PyMuPDF + pikepdf + pdfplumber

- **PyMuPDF (fitz):** Fastest PDF-to-image rendering (C-based). Used for page rendering, native text extraction via `get_text("blocks")`, and text layer detection.
- **pikepdf:** Used for PDF repair (corrupt files) and Python-native compression. Can handle damaged xref tables that crash other libraries.
- **pdfplumber:** Reserved for table extraction if needed (not used in the current pipeline but available as a dependency).

### Storage: Local Filesystem + Adapter

**Choice:** Local filesystem with UUID-based paths.

**Why:** Simplest setup for development and evaluation. The `StorageService` abstract class in `app/services/storage_service.py` enables swapping to S3/MinIO without changing any pipeline or API code. UUID paths prevent any possibility of client-controlled paths reaching the filesystem.

### Auth: JWT (python-jose + passlib/bcrypt)

Stateless JWT tokens with bcrypt password hashing. No session storage needed, scales horizontally with any number of API instances.

## 3. File Handling & Size Constraints

### Graduated Size Policy

| Size Range | Action |
|---|---|
| 0 – `MAX_UPLOAD_SIZE_SOFT_MB` (15 MB) | Accept as-is, no compression |
| `MAX_UPLOAD_SIZE_SOFT_MB` – `MAX_UPLOAD_SIZE_HARD_MB` (15-50 MB) | Accept, store raw copy for audit, compress in worker before extraction |
| > `MAX_UPLOAD_SIZE_HARD_MB` (50 MB) | Reject with 413 and helpful message |

### Compression Strategy

**PDFs:**
1. Try Ghostscript with `/ebook` preset (150 DPI) → check if under target
2. Fall back to `/screen` preset (72 DPI) → check again
3. Fall back to pikepdf stream compression
4. If still over limit, proceed anyway with a quality warning review flag

**Images:**
1. Resize to `MAX_IMAGE_DIMENSION_PX` (4000px) on long edge
2. Convert PNG without transparency to JPEG
3. Progressive JPEG quality stepping: 85 → 70 → 55 → 40 until under target

### Auditability
- `original_size_bytes` and `stored_size_bytes` always recorded
- `compression_applied` boolean flag on document record
- Compression ratio logged server-side
- Original file preserved in `raw/` bucket path

### Page Count Guard
- PDFs exceeding `MAX_PAGE_COUNT` (300) are processed partially (first N pages)
- Document status set to `PARTIAL`
- `pages_processed` and `pages_skipped` recorded
- Review item created noting which pages were skipped

### Why These Numbers
- **50 MB hard limit:** Covers 99%+ of exam papers. Larger files are typically scanning errors.
- **15 MB soft limit:** Optimization target. Most well-scanned exam papers are under 10 MB after compression.
- **300 pages:** Maximum for any real exam paper. Prevents worker timeout on enormous documents.
- **200 DPI target:** Optimal for OCR accuracy vs. file size. Below 150 DPI, OCR accuracy degrades significantly.

## 4. Security Mitigation Table

| # | Risk | Mitigation | Status | Code Location |
|---|------|-----------|--------|---------------|
| 1 | Spoofed file type | python-magic content sniffing; MIME allowlist | ✅ Implemented | `services/file_validator.py` |
| 2 | Oversized upload / zip-bomb | Hard size cap + Pillow MAX_IMAGE_PIXELS + page count guard | ✅ Implemented | `file_validator.py`, `stage1_validation.py` |
| 3 | Malicious PDF (JS, exploits) | pikepdf/PyMuPDF sandboxed open with timeout; never eval JS; log-only warning | ✅ Implemented | `stage1_validation.py` |
| 4 | Path traversal via filename | UUID-based storage paths; original filename sanitized for display only | ✅ Implemented | `storage_service.py`, `documents.py` |
| 5 | Unauthorized access | Row-level ownership check; 404 not 403 for non-owners | ✅ Implemented | `dependencies.py` |
| 6 | Credential leakage | pydantic-settings from env; .env in .gitignore; .env.example with dummies | ✅ Implemented | `config.py`, `.gitignore` |
| 7 | Virus/malware | Pluggable adapter interface; ClamAV impl + stub | ⚠️ Stub only | `adapters/virus_scanner.py` |
| 8 | Worker crash / stuck job | acks_late + retry w/backoff + stale job reaper (beat) | ✅ Implemented | `celery_app.py`, `tasks.py` |
| 9 | Upload DoS | Redis-backed sliding window rate limiter | ✅ Implemented | `services/rate_limiter.py` |
| 10 | SQL injection | SQLAlchemy ORM only; Pydantic validation on all inputs | ✅ Implemented | All models/schemas |
| 11 | Direct file access | Authenticated streaming endpoint; no static file serving | ✅ Implemented | `documents.py` (get_page_image) |
| 12 | Internal error leakage | Global exception handler returns generic message; real error logged | ✅ Implemented | `main.py` |

### Documented Limitations

- **ClamAV virus scanning:** Implemented as a pluggable stub (`VirusScannerStub`). In production, set `VIRUS_SCAN_ENABLED=true` and run a ClamAV daemon. The interface is fully defined and tested.
- **LLM-assisted segmentation:** Stub only (`LLMAdapterStub`). The regex + heuristic pipeline handles common exam paper formats. For ambiguous layouts, wire in an LLM provider via the adapter interface.
- **Nginx/reverse proxy size limits:** Not configured in this project (runs behind uvicorn directly). In production, set `client_max_body_size` in nginx to match `MAX_UPLOAD_SIZE_HARD_MB`.

## 5. Confidence Scoring Formula

### Composite Score

```
confidence = (W_ocr × S_ocr) + (W_num × S_num) + (W_opt × S_opt) + (W_bnd × S_bnd) + (W_ans × S_ans)
```

### Signals and Weights (configurable via environment)

| Signal | Weight (default) | Score 1.0 | Score 0.5 | Score 0.0 |
|--------|:---:|---|---|---|
| **OCR confidence** (`S_ocr`) | 0.30 | Avg word confidence ≥ 90% | 50-90% | < 50% |
| **Number detection** (`S_num`) | 0.20 | Regex pattern match | Positional inference | Not detected |
| **Option completeness** (`S_opt`) | 0.20 | All 4 options found | 2-3 options | 0-1 options (MCQ) |
| **Boundary quality** (`S_bnd`) | 0.15 | Clean start + clean end | Partial | Empty text |
| **Answer match** (`S_ans`) | 0.15 | Exact number match | Fuzzy match | Not found |

### Thresholds

| Range | Action |
|---|---|
| `≥ 0.85` | Auto-accept |
| `0.50 – 0.84` | Flag for review (severity: MEDIUM) |
| `< 0.50` | Mark UNRELIABLE (severity: HIGH) |

### Review Item Data Retention

Every review-flagged item stores:
- Original page image reference (via `source_pages` → `pages.image_path`)
- Raw OCR text (`questions.raw_text`)
- Specific reason string (e.g., "Low confidence (0.42): low OCR confidence (0.35); incomplete options (2/4)")

## 6. Data Model

9 tables connected via foreign keys. See `alembic/versions/001_initial_schema.py` for the full DDL.

Key relationships:
- `users` → owns → `documents`
- `documents` → contains → `pages`, `questions`, `processing_jobs`
- `documents` ↔ linked via → `document_links`
- `questions` → has → `options`, `answer`
- `review_items` → references → any entity (polymorphic via `entity_type` + `entity_id`)

## 7. API Design Decisions

### Async Upload Pattern
- `POST /documents` returns `202 Accepted` immediately with `document_id`
- Client polls `GET /documents/{id}/status` for progress
- This prevents HTTP timeouts for large documents

### Ownership & Privacy
- Every query includes `WHERE owner_id = current_user.id`
- Non-owned resources return `404` (not `403`) to prevent existence leakage
- Page images served only through authenticated streaming endpoints

### Pagination
- All list endpoints use page-based pagination with configurable `page_size`
- Total count and total pages included in response envelope

## 8. Deployment Considerations

### Horizontal Scaling
- **API:** Multiple uvicorn instances behind a load balancer
- **Workers:** Multiple Celery workers via `--concurrency` or additional containers
- **Database:** Single PostgreSQL (vertically scale, or read replicas for queries)
- **Redis:** Single instance sufficient for moderate load; Redis Cluster for high load

### Monitoring
- **Flower** (port 5555): Real-time Celery task monitoring
- **Health endpoint** (`/healthz`): Load balancer health checks
- **Processing jobs table**: Audit trail of all pipeline stages with timings
- **Structured logging**: JSON-compatible log format for aggregation
