# Pragati Bharati — Document Intelligence & Question Extraction Service

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-41%2F41%20Passed%20(100%25)-brightgreen)](tests/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **Engineering Assignment — Full Stack Developer (Round 2)**  
> A scalable, production-oriented document processing pipeline and REST API designed for ed-tech platforms to ingest unstructured exam papers (digital PDFs, scanned images, camera photos) and convert them into structured, machine-readable questions with answer-key association, composite confidence scoring, and human-in-the-loop review queues.

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [System Architecture](#system-architecture)
- [Core Features & Pipeline Stages](#core-features--pipeline-stages)
- [Quick Start with Docker](#quick-start-with-docker)
- [API Surface & Endpoints](#api-surface--endpoints)
- [Demonstration & Evaluation Scenarios](#demonstration--evaluation-scenarios)
- [Security & File Handling Matrix](#security--file-handling-matrix)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Repository Structure](#repository-structure)
- [Design Decisions & Trade-Offs](#design-decisions--trade-offs)

---

## Executive Summary

Educational institutions and assessment platforms receive exam papers, question banks, and answer keys across heterogeneous formats:
* Digitally typeset PDFs with native vector text
* Distorted, skewed, or low-resolution camera photos and scans
* Multi-page examinations where questions and options span across page boundaries
* Separate answer keys that must be fuzzy-matched and linked post-upload

**Pragati Bharati Document Intelligence Service** addresses these real-world challenges through an asynchronous, decoupled architecture. High-cost OCR, text segmentation, and confidence scoring are offloaded to distributed background workers, ensuring the REST API remains responsive (HTTP 202 Accepted) with immediate UUID tracking.

---

## System Architecture

```
┌─────────────────┐       JWT Auth       ┌──────────────────────────────────────────────┐
│  Client / Apps  │ ───────────────────> │              FastAPI Backend                 │
│ (Swagger / API) │                      │     /auth, /documents, /questions,           │
└─────────────────┘                      │     /review-queue, /healthz, /docs           │
                                         └──────────────────────┬───────────────────────┘
                                                                │
                                         ┌──────────────────────┼───────────────────────┐
                                         │                      │                       │
                                         ▼                      ▼                       ▼
                                  ┌──────────────┐      ┌───────────────┐       ┌───────────────┐
                                  │  PostgreSQL  │      │     Redis     │       │ Local / S3    │
                                  │  (Metadata,  │      │ (Broker/Queue │       │ Object Store  │
                                  │   Questions) │      │  Rate Limit)  │       │ (Raw/Pages)   │
                                  └──────────────┘      └───────┬───────┘       └───────┬───────┘
                                                                │                       │
                                                                ▼                       │
                                                    ┌───────────────────────────┐       │
                                                    │    Celery Worker Pool     │ <─────┘
                                                    │  Stage 1: Validation      │
                                                    │  Stage 2: Preprocessing   │
                                                    │  Stage 3: Extraction      │
                                                    │  Stage 4: Segmentation    │
                                                    │  Stage 5: Answer Key      │
                                                    │  Stage 6: Confidence      │
                                                    └───────────────────────────┘
```

---

## Core Features & Pipeline Stages

The backend pipeline executes **6 sequential, fault-tolerant stages**:

1. **Stage 1 — Validation & Self-Healing Normalization:**
   - **MIME Sniffing:** Uses `libmagic` byte inspection (never trusts file extensions).
   - **PDF Auto-Repair:** Automatically recovers damaged xref tables via `pikepdf` before falling back to `PyMuPDF`.
   - **EXIF Auto-Rotation:** Detects camera orientation metadata (90°, 180°, 270°) and rotates images before OCR.
   - **Graduated Size Policy:** Constrains and downsamples oversized files in background using Ghostscript & `pikepdf`.

2. **Stage 2 — Image Preprocessing:**
   - Renders PDF pages to 200 DPI normalized images (optimal balance of OCR accuracy vs. memory).
   - Deskewing and contrast enhancement for degraded scans.

3. **Stage 3 — Dual-Mode Extraction:**
   - **Digital PDFs:** Ultra-fast native vector text extraction via `PyMuPDF` block bounding boxes.
   - **Scanned Documents & Images:** High-accuracy `Tesseract OCR` with per-word confidence metrics.

4. **Stage 4 — Segmentation & Multi-Page Stitching:**
   - Robust regular expressions handle varied numbering formats: `1.`, `Q.1`, `1)`, `Question 1`.
   - Option extraction: `(A)`, `A.`, `A)`, `[A]`.
   - **Cross-Page Continuity:** Stitches questions that span across page boundaries and tracks `source_pages: [1, 2]`.

5. **Stage 5 — Answer Key Association:**
   - **Intra-document:** Identifies answer keys located at the beginning or end of the document.
   - **Inter-document:** Supports cross-document linking via `/documents/{id}/link` for separate answer key PDFs.

6. **Stage 6 — Composite Confidence & Human-in-the-Loop:**
   - Calculates weighted composite confidence score $C \in [0.0, 1.0]$ based on OCR clarity, option completeness, and syntax validity.
   - **Thresholds:**
     - $\ge 0.85$: Auto-accepted.
     - $0.50 - 0.85$: Routed to `/review-queue` for human verification.
     - $< 0.50$: Flagged as unreliable extraction.

---

## Quick Start with Docker

### Prerequisites
- Docker & Docker Compose (v2+)

### Run with a Single Command

```bash
# 1. Clone the repository
git clone https://github.com/themanideep009/PBNC-Company-Assignment-.git
cd PBNC-Company-Assignment-

# 2. Setup environment file
cp .env.example .env

# 3. Start all services in background
docker-compose up --build -d
```

### Live Service Interfaces

| Service | URL | Description |
| :--- | :--- | :--- |
| **Interactive Swagger UI** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API exploration and test runner |
| **ReDoc Specification** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean, structured OpenAPI documentation |
| **Service Health Check** | [http://localhost:8000/healthz](http://localhost:8000/healthz) | Live database and Redis connectivity monitor |
| **Celery Flower Dashboard** | [http://localhost:5555](http://localhost:5555) | Real-time queue, worker, and task monitoring |

---

## API Surface & Endpoints

| Category | Method | Endpoint | Auth | Description |
| :--- | :---: | :--- | :---: | :--- |
| **Auth** | `POST` | `/auth/register` | No | Register new user account |
| | `POST` | `/auth/login` | No | Authenticate and obtain JWT bearer token |
| **Documents** | `POST` | `/documents` | Yes | Upload document (PDF / PNG / JPEG) |
| | `GET` | `/documents` | Yes | List user's documents (paginated) |
| | `GET` | `/documents/{id}/status` | Yes | Check processing stage and compression stats |
| | `POST` | `/documents/{id}/link` | Yes | Link separate Answer Key PDF to question paper |
| | `GET` | `/documents/{id}/questions` | Yes | Retrieve all structured extracted questions |
| | `GET` | `/documents/{id}/pages/{n}/image` | Yes | Stream rendered page image for visual verification |
| **Questions** | `GET` | `/questions/{id}` | Yes | Detailed question payload with options |
| | `GET` | `/questions/{id}/answer` | Yes | Question answer and matching confidence |
| **Review Queue** | `GET` | `/review-queue` | Yes | List questions flagged for human review |
| | `PATCH` | `/review-queue/{id}` | Yes | Mark review item as resolved |
| **System** | `GET` | `/healthz` | No | Liveness & readiness probe |

---

## Demonstration & Evaluation Scenarios

The system includes pre-generated sample documents in `sample_data/inputs/` and automated execution evidence in `DEMO_EVIDENCE.md`:

```
sample_data/
├── inputs/
│   ├── sample_exam_digital.pdf     # Clean digital PDF with MCQs
│   ├── sample_exam_multi_page.pdf  # 2-page exam with question spanning across pages
│   ├── sample_exam_scanned.pdf     # Scanned-style raster PDF (OCR test)
│   ├── sample_exam_scan.png        # High-resolution image scan
│   ├── sample_answer_key.pdf       # Dedicated separate answer key document
│   ├── corrupt_file.pdf            # Corrupt PDF to demonstrate self-healing / error handling
│   └── spoofed_exe.pdf             # Disguised executable to verify MIME sniffing
└── outputs/
    ├── sample_batch_output.json    # Complete structured JSON output
    └── sample_question_output.json # Individual question JSON representation
```

### Sample Output Format

```json
{
  "question_id": "6f70f20d-59c4-4b13-a5aa-b28263675244",
  "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
  "question_number": "1",
  "question_text": "What is the primary organelle responsible for ATP production in eukaryotic cells?",
  "question_type": "MCQ",
  "options": [
    { "label": "A", "text": "Nucleus" },
    { "label": "B", "text": "Mitochondria" },
    { "label": "C", "text": "Ribosome" },
    { "label": "D", "text": "Endoplasmic Reticulum" }
  ],
  "answer": {
    "value": "ANSWER: (B) MITOCHONDRIA",
    "source": "LINKED_DOC",
    "match_confidence": 0.95,
    "review_required": false
  },
  "source_pages": [1],
  "extraction_confidence": 0.9325,
  "review_required": false
}
```

---

## Security & File Handling Matrix

| # | Threat / Risk | Implemented Defense | Code Location |
|---|---------------|---------------------|---------------|
| 1 | **MIME Type Spoofing** | Content sniffing via `python-magic` on raw byte headers | `services/file_validator.py` |
| 2 | **Decompression Bomb** | Pillow `MAX_IMAGE_PIXELS = 200,000,000` cap + page count limit | `file_validator.py`, `stage1_validation.py` |
| 3 | **Corrupt / Broken PDFs** | `pikepdf` xref rebuild with fallback to `PyMuPDF` stream recovery | `stage1_validation.py` |
| 4 | **Path Traversal Attacks** | UUID4 internal storage filenames; client filename sanitized for display | `storage_service.py`, `documents.py` |
| 5 | **Information Leakage** | Row-level tenant isolation returning 404 (not 403) for non-owned items | `core/dependencies.py` |
| 6 | **Embedded JavaScript** | PDF JavaScript detection and suppression without execution | `stage1_validation.py` |
| 7 | **Worker Crash / Deadlocks** | Celery `acks_late` re-dispatch + Celery Beat stale job reaper | `celery_app.py`, `tasks.py` |
| 8 | **Upload Abuse (DoS)** | Redis sliding-window token bucket rate limiter | `services/rate_limiter.py` |

---

## Testing & Quality Assurance

The codebase includes full unit, integration, and security test suites using `pytest`:

```bash
# Run tests inside Docker container
docker exec pbnccompany-api-1 pytest -v
```

### Test Results
```text
tests/test_auth.py                     .......... [ 24%] PASSED (10/10)
tests/test_documents.py                .........  [ 46%] PASSED (9/9)
tests/test_pipeline/test_segmentation.py ...............  [ 82%] PASSED (15/15)
tests/test_security.py                 .......    [100%] PASSED (7/7)

============================== 41 passed in 8.51s ==============================
```

---

## Repository Structure

```
PBNC-Company-Assignment/
├── alembic/                  # Database migration scripts (PostgreSQL schema)
│   └── versions/             # Versioned schema migrations
├── app/
│   ├── adapters/             # Pluggable OCR, LLM, and Virus scanner adapters
│   ├── api/                  # FastAPI routers and route handlers
│   ├── core/                 # Config (Pydantic), security, database session, Celery app
│   ├── models/               # SQLAlchemy ORM models (10 relations)
│   ├── schemas/              # Pydantic validation and serialization models
│   ├── services/             # File validator, compression, rate limiter, storage
│   ├── workers/              # Celery background tasks
│   │   └── pipeline/         # 6-stage async extraction pipeline
│   └── main.py               # FastAPI application factory & lifespan
├── postman/                  # Postman collection for manual/automated API testing
├── sample_data/
│   ├── inputs/               # Sample digital, scanned, multi-page, and corrupt documents
│   └── outputs/              # Sample JSON extraction output files
├── scripts/                  # Synthetic test generation and automated demo runners
├── tests/                    # 41 unit and integration tests (Pytest)
├── ARCHITECTURE.md           # In-depth architectural rationale and trade-offs
├── DEMO_EVIDENCE.md          # Output logs verifying all 10 demonstration scenarios
├── docker-compose.yml        # Multi-container orchestration (API, Worker, Beat, Flower, DB, Redis)
├── Dockerfile                # Production API Docker container
├── Dockerfile.worker         # Production Celery worker container with Tesseract & Ghostscript
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## Design Decisions & Trade-Offs

* **Why FastAPI + Celery?** FastAPI provides native async request handling and auto-generated OpenAPI documentation. Celery provides battle-tested task acknowledgment (`acks_late`), exponential retry backoffs, and scheduling capabilities essential for heavy document workloads.
* **Why PyMuPDF + Tesseract?** PyMuPDF provides sub-millisecond vector text extraction for clean digital PDFs, bypassing OCR entirely. Tesseract is used selectively only when pages lack embedded text layers, minimizing CPU overhead.
* **Adapter Pattern for Extensibility:** OCR and LLM layers are encapsulated behind abstract base classes (`OCRAdapter`, `LLMAdapter`), allowing cloud document AI (AWS Textract, Google Document AI) or LLM re-ranking to be plugged in via configuration without rewriting pipeline logic.

---

## License

This project is licensed under the MIT License.
