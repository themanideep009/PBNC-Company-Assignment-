"""
Celery application instance and configuration.

Design decisions (documented in ARCHITECTURE.md):
- Celery chosen over RQ (limited retry/timeout features) and Arq (smaller ecosystem).
- Redis serves as both broker and result backend for operational simplicity.
- Workers are configured with per-task timeouts and retry-with-exponential-backoff.
- max-tasks-per-child=50 prevents memory leaks from long-running image processing.
- Beat schedule includes a stale job reaper to prevent permanently stuck PROCESSING jobs.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pragati_bharati",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.set_default()

celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIMEOUT + 60,  # Hard kill after this
    task_soft_time_limit=settings.CELERY_TASK_TIMEOUT,   # Raises SoftTimeLimitExceeded
    task_acks_late=True,                                  # Re-queue if worker crashes mid-task
    worker_prefetch_multiplier=1,                         # Fair scheduling for long tasks

    # Retry defaults
    task_default_retry_delay=30,       # 30 seconds initial retry delay
    task_max_retries=settings.CELERY_TASK_MAX_RETRIES,

    # Routing
    task_default_queue="document_processing",
    task_routes={
        "app.workers.tasks.*": {"queue": "document_processing"},
    },

    # Result expiry
    result_expires=86400,  # 24 hours

    # Beat schedule: stale job reaper runs every 10 minutes
    beat_schedule={
        "reap-stale-jobs": {
            "task": "app.workers.tasks.reap_stale_jobs",
            "schedule": crontab(minute="*/10"),
        },
    },
)

# Auto-discover tasks in app.workers.tasks
celery_app.autodiscover_tasks(["app.workers"])
