"""
Celery task definitions — document processing orchestration.

Main task: process_document
- Orchestrates all 6 pipeline stages sequentially
- Updates document status and processing job records at each stage
- Handles timeouts, retries, and failure states
- Never leaves a document stuck in PROCESSING (stale job reaper catches edge cases)

Supporting tasks:
- process_answer_key_linking: Re-runs answer matching when docs are linked post-processing
- reap_stale_jobs: Periodic task to catch and fail stuck jobs
"""

import logging
import traceback
from datetime import datetime, timezone, timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.answer import Answer, AnswerSource
from app.models.document import Document, DocumentStatus
from app.models.option import Option
from app.models.page import Page
from app.models.processing_job import ProcessingJob, JobStatus, PipelineStage
from app.models.question import Question
from app.models.review_item import ReviewItem, EntityType, ReviewSeverity

logger = logging.getLogger(__name__)
settings = get_settings()


@shared_task(
    bind=True,
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
    default_retry_delay=30,
    soft_time_limit=settings.CELERY_TASK_TIMEOUT,
    time_limit=settings.CELERY_TASK_TIMEOUT + 60,
    acks_late=True,
    reject_on_worker_lost=True,
    name="app.workers.tasks.process_document",
)
def process_document(self, document_id: str):
    """
    Main document processing pipeline.

    Runs all 6 stages sequentially:
    1. Validation & Normalization
    2. Preprocessing (page images)
    3. Text/OCR Extraction
    4. Question Segmentation
    5. Answer Key Detection
    6. Confidence Scoring & Review Flags
    """
    db = SessionLocal()

    try:
        # Fetch document
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            logger.error(f"Document {document_id} not found")
            return

        # Update status to PROCESSING
        document.status = DocumentStatus.PROCESSING
        document.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Starting pipeline for document {document_id}: {document.filename}")

        # ── Stage 1: Validation & Normalization ─────────────────────────
        stage1_job = _create_job(db, document_id, PipelineStage.VALIDATION)
        try:
            from app.workers.pipeline.stage1_validation import run_stage1

            stage1_result = run_stage1(
                document_id=document_id,
                storage_path=document.storage_path,
                mime_type=document.mime_type,
            )

            # Update document with Stage 1 results
            document.stored_size_bytes = stage1_result["stored_size_bytes"]
            document.compression_applied = stage1_result["compression_applied"]
            document.page_count = stage1_result["page_count"]
            document.pages_processed = stage1_result["pages_to_process"]
            document.pages_skipped = stage1_result["pages_skipped"]

            if stage1_result["is_partial"]:
                document.status = DocumentStatus.PARTIAL

            # Create review items for quality warnings
            for warning in stage1_result.get("quality_warnings", []):
                _create_review_item(
                    db, document_id, EntityType.DOCUMENT,
                    document_id, warning, ReviewSeverity.LOW,
                )

            _complete_job(db, stage1_job, {"result": "success", **stage1_result})
            db.commit()

        except Exception as e:
            _fail_job(db, stage1_job, str(e))
            raise

        # ── Stage 2: Preprocessing ──────────────────────────────────────
        stage2_job = _create_job(db, document_id, PipelineStage.PREPROCESSING)
        try:
            from app.workers.pipeline.stage2_preprocessing import run_stage2

            page_data_list = run_stage2(
                document_id=document_id,
                processed_path=stage1_result["processed_path"],
                mime_type=document.mime_type,
                pages_to_process=stage1_result["pages_to_process"] or 1,
            )

            _complete_job(db, stage2_job, {
                "pages_processed": len(page_data_list),
            })
            db.commit()

        except Exception as e:
            _fail_job(db, stage2_job, str(e))
            raise

        # ── Stage 3: Text/OCR Extraction ────────────────────────────────
        stage3_job = _create_job(db, document_id, PipelineStage.EXTRACTION)
        try:
            from app.workers.pipeline.stage3_extraction import run_stage3

            page_data_list = run_stage3(page_data_list)

            # Persist page records
            for page_data in page_data_list:
                page = Page(
                    document_id=document_id,
                    page_number=page_data["page_number"],
                    image_path=page_data.get("image_path"),
                    ocr_text=page_data.get("ocr_text"),
                    native_text=page_data.get("native_text"),
                    rotation_applied=page_data.get("rotation_applied", 0.0),
                    ocr_confidence=page_data.get("ocr_confidence"),
                    quality_flags=page_data.get("quality_flags", {}),
                )
                db.add(page)

            _complete_job(db, stage3_job, {
                "pages_extracted": len(page_data_list),
                "methods": [p.get("extraction_method", "unknown") for p in page_data_list],
            })
            db.commit()

        except Exception as e:
            _fail_job(db, stage3_job, str(e))
            raise

        # ── Stage 4: Question Segmentation ──────────────────────────────
        stage4_job = _create_job(db, document_id, PipelineStage.SEGMENTATION)
        try:
            from app.workers.pipeline.stage4_segmentation import run_stage4

            questions = run_stage4(page_data_list)

            _complete_job(db, stage4_job, {
                "questions_found": len(questions),
                "types": {q.question_type: 0 for q in questions},
            })
            db.commit()

        except Exception as e:
            _fail_job(db, stage4_job, str(e))
            raise

        # ── Stage 5: Answer Key Detection ───────────────────────────────
        stage5_job = _create_job(db, document_id, PipelineStage.ANSWER_KEY)
        try:
            from app.workers.pipeline.stage5_answer_key import (
                run_stage5, get_linked_document_text,
            )

            # Check for linked answer key documents
            linked_text = get_linked_document_text(document_id, db)

            answers = run_stage5(questions, page_data_list, linked_text)

            _complete_job(db, stage5_job, {
                "answers_found": len(answers),
                "from_linked_doc": linked_text is not None,
            })
            db.commit()

        except Exception as e:
            _fail_job(db, stage5_job, str(e))
            raise

        # ── Stage 6: Confidence & Review ────────────────────────────────
        stage6_job = _create_job(db, document_id, PipelineStage.CONFIDENCE)
        try:
            from app.workers.pipeline.stage6_confidence import run_stage6

            scored_questions = run_stage6(questions, answers, page_data_list)

            # Persist questions, options, answers, and review items
            for scored in scored_questions:
                q = scored["question"]
                question_record = Question(
                    document_id=document_id,
                    question_number=q.question_number,
                    question_text=q.question_text,
                    question_type=q.question_type,
                    source_pages=q.source_pages,
                    extraction_confidence=scored["confidence"],
                    review_required=scored["review_required"],
                    review_reason=scored["review_reason"],
                    raw_text=q.raw_text,
                )
                db.add(question_record)
                db.flush()  # Get question ID

                # Persist options
                for i, opt in enumerate(q.options):
                    option_record = Option(
                        question_id=question_record.id,
                        label=opt.label,
                        text=opt.text,
                        image_path=opt.image_path,
                        sort_order=i,
                    )
                    db.add(option_record)

                # Persist answer
                answer = scored.get("answer")
                if answer:
                    answer_record = Answer(
                        question_id=question_record.id,
                        answer_value=answer.answer_value,
                        source=answer.source,
                        match_confidence=answer.match_confidence,
                        review_required=answer.match_type != "exact",
                    )
                    db.add(answer_record)
                else:
                    # Create a NONE_FOUND answer record
                    answer_record = Answer(
                        question_id=question_record.id,
                        answer_value=None,
                        source=AnswerSource.NONE_FOUND,
                        match_confidence=0.0,
                        review_required=q.question_type in ("MCQ", "TRUE_FALSE"),
                    )
                    db.add(answer_record)

                # Create review items for flagged questions
                if scored["review_required"]:
                    _create_review_item(
                        db, document_id, EntityType.QUESTION,
                        str(question_record.id),
                        scored["review_reason"] or "Low confidence extraction",
                        scored["review_severity"],
                    )

            _complete_job(db, stage6_job, {
                "questions_scored": len(scored_questions),
                "auto_accepted": sum(1 for s in scored_questions if not s["review_required"]),
                "flagged_for_review": sum(1 for s in scored_questions if s["review_required"]),
            })

            # Final status update
            if document.status != DocumentStatus.PARTIAL:
                document.status = DocumentStatus.COMPLETED
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                f"Pipeline completed for document {document_id}: "
                f"{len(scored_questions)} questions extracted"
            )

        except Exception as e:
            _fail_job(db, stage6_job, str(e))
            raise

    except SoftTimeLimitExceeded:
        logger.error(f"Document {document_id} processing timed out")
        document.status = DocumentStatus.FAILED
        document.error_message = "Processing timed out"
        document.updated_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        logger.error(
            f"Pipeline failed for document {document_id}: {e}\n"
            f"{traceback.format_exc()}"
        )
        # Mark document as failed
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = DocumentStatus.FAILED
                document.error_message = f"Processing failed: {str(e)[:500]}"
                document.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass

        # Retry if not max retries
        if self.request.retries < settings.CELERY_TASK_MAX_RETRIES:
            raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))

    finally:
        db.close()


@shared_task(
    name="app.workers.tasks.process_answer_key_linking",
    soft_time_limit=300,
    time_limit=360,
)
def process_answer_key_linking(question_doc_id: str, answer_key_doc_id: str):
    """
    Re-run answer key matching after two documents are linked.

    Called when a user links an answer key to a question paper after
    both have already been processed.
    """
    db = SessionLocal()
    try:
        from app.workers.pipeline.stage5_answer_key import (
            run_stage5, get_linked_document_text,
        )
        from app.workers.pipeline.stage4_segmentation import ExtractedQuestion

        # Get existing questions
        existing_questions = db.query(Question).filter(
            Question.document_id == question_doc_id
        ).order_by(Question.question_number).all()

        if not existing_questions:
            logger.warning(f"No questions found for document {question_doc_id}")
            return

        # Convert to ExtractedQuestion format for Stage 5
        questions = []
        for eq in existing_questions:
            questions.append(ExtractedQuestion(
                question_number=eq.question_number,
                question_text=eq.question_text,
                question_type=eq.question_type,
                source_pages=eq.source_pages or [],
                number_detected_by="regex",
            ))

        # Get linked document text
        linked_text = get_linked_document_text(question_doc_id, db)

        if not linked_text:
            logger.warning(f"No text found in linked answer key for {question_doc_id}")
            return

        # Get page data for confidence scoring
        pages = db.query(Page).filter(
            Page.document_id == question_doc_id
        ).order_by(Page.page_number).all()
        page_data_list = [
            {
                "page_number": p.page_number,
                "ocr_confidence": p.ocr_confidence or 0.5,
            }
            for p in pages
        ]

        # Run answer matching
        answers = run_stage5(questions, page_data_list, linked_text)

        # Update existing answer records
        for eq, q in zip(existing_questions, questions):
            answer_data = answers.get(q.question_number)
            if answer_data:
                existing_answer = db.query(Answer).filter(
                    Answer.question_id == eq.id
                ).first()

                if existing_answer:
                    existing_answer.answer_value = answer_data.answer_value
                    existing_answer.source = answer_data.source
                    existing_answer.match_confidence = answer_data.match_confidence
                    existing_answer.review_required = answer_data.match_type != "exact"
                else:
                    new_answer = Answer(
                        question_id=eq.id,
                        answer_value=answer_data.answer_value,
                        source=answer_data.source,
                        match_confidence=answer_data.match_confidence,
                        review_required=answer_data.match_type != "exact",
                    )
                    db.add(new_answer)

        db.commit()
        logger.info(
            f"Answer key linking complete: {len(answers)} answers matched "
            f"for document {question_doc_id}"
        )

    except Exception as e:
        logger.error(f"Answer key linking failed: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


@shared_task(name="app.workers.tasks.reap_stale_jobs")
def reap_stale_jobs():
    """
    Periodic task (Celery Beat): find and fail documents stuck in PROCESSING.

    Runs every 10 minutes. Documents stuck in PROCESSING for longer than
    CELERY_STALE_JOB_THRESHOLD_MINUTES are marked as FAILED with a reason.

    This prevents documents from being permanently stuck if a worker crashes
    mid-processing without the acks_late retry kicking in.
    """
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.CELERY_STALE_JOB_THRESHOLD_MINUTES
        )

        stale_docs = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSING,
            Document.updated_at < threshold,
        ).all()

        if stale_docs:
            logger.warning(f"Found {len(stale_docs)} stale documents in PROCESSING state")

        for doc in stale_docs:
            doc.status = DocumentStatus.FAILED
            doc.error_message = (
                f"Processing stalled — no progress for "
                f"{settings.CELERY_STALE_JOB_THRESHOLD_MINUTES} minutes. "
                f"The document may need to be re-uploaded."
            )
            doc.updated_at = datetime.now(timezone.utc)

            logger.warning(
                f"Marked stale document {doc.id} ({doc.filename}) as FAILED"
            )

        if stale_docs:
            db.commit()

    except Exception as e:
        logger.error(f"Stale job reaper error: {e}")
    finally:
        db.close()


# ── Helper Functions ──────────────────────────────────────────────────────


def _create_job(db, document_id: str, stage: str) -> ProcessingJob:
    """Create a processing job record for a pipeline stage."""
    job = ProcessingJob(
        document_id=document_id,
        stage=stage,
        status=JobStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Stage {stage} started for document {document_id}")
    return job


def _complete_job(db, job: ProcessingJob, log_data: dict):
    """Mark a processing job as completed."""
    job.status = JobStatus.COMPLETED
    job.finished_at = datetime.now(timezone.utc)
    job.log = log_data
    db.add(job)


def _fail_job(db, job: ProcessingJob, error: str):
    """Mark a processing job as failed."""
    job.status = JobStatus.FAILED
    job.finished_at = datetime.now(timezone.utc)
    job.log = {"error": error[:1000]}
    db.add(job)
    db.commit()
    logger.error(f"Stage {job.stage} failed: {error}")


def _create_review_item(
    db, document_id: str, entity_type: str,
    entity_id: str, reason: str, severity: str,
):
    """Create a review item for flagged content."""
    review = ReviewItem(
        document_id=document_id,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        severity=severity,
    )
    db.add(review)
