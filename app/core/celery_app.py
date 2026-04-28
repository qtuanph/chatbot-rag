"""
Celery application configuration.

Reliability settings (most important):
  - task_acks_late=True: ACK task AFTER completion, not when received.
    If the worker crashes mid-task, the broker re-queues it automatically.
  - task_reject_on_worker_lost=True: Explicit requeue on unexpected worker death.
  - worker_prefetch_multiplier=1: Each worker holds exactly 1 task at a time.
    Docling + PaddleOCR tasks are heavy; hoarding multiple tasks wastes memory
    and causes unfair load distribution.

Memory safety:
  - worker_max_memory_per_child=1.5GB: Kill child process if RSS exceeds limit.
    Prevents memory leaks from large PDF processing accumulating over time.

Broker reliability:
  - visibility_timeout=7200s: Redis re-delivery guard — tasks running >2h
    are assumed lost. Longest expected task is OCR/parse (~30 min).
  - broker_connection_retry_on_startup=True: Don't crash if Redis unavailable.

Queue routing:
  - ingestion: upload-pipeline worker (GPU-bound embedding tasks)
  - cleanup: cleanup-pipeline worker (lightweight delete + beat tasks)
  - default: fallback queue

Time limits (prevent hung parse tasks):
  - task_soft_time_limit: Raises SoftTimeLimitExceeded → worker catches it,
    updates document status to 'failed', then exits gracefully.
  - task_time_limit: Hard kill after this; should be > soft limit.
"""

from celery import Celery

from app.core.config import settings

_all_modules = ["app.workers.upload_pipeline", "app.workers.cleanup_pipeline"]
_include_map = {
    "upload": ["app.workers.upload_pipeline"],
    "cleanup": ["app.workers.cleanup_pipeline"],
}

celery_app = Celery(
    "chatbot_rag",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=_include_map.get(settings.celery_include, _all_modules),
)

celery_app.conf.update(
    # ── Reliability ───────────────────────────────────────────────────────────
    task_acks_late=True,  # ACK after task completes, not when received
    task_reject_on_worker_lost=True,  # Requeue if worker dies mid-task
    # ── Performance ───────────────────────────────────────────────────────────
    worker_prefetch_multiplier=1,  # 1 task per worker — fair distribution
    worker_disable_rate_limits=True,  # Rate limit at API level, not Celery
    # ── Memory safety ─────────────────────────────────────────────────────────
    worker_max_memory_per_child=settings.celery_worker_max_memory_kb,
    # ── Time limits (Docling + PaddleOCR can be slow on large PDFs) ────────────
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    # ── Broker ────────────────────────────────────────────────────────────────
    broker_connection_retry_on_startup=True,  # Don't crash if Redis not ready
    broker_transport_options={
        "visibility_timeout": settings.celery_visibility_timeout,
        "fanout_prefix": True,
    },
    # ── Result backend ────────────────────────────────────────────────────────
    result_expires=settings.celery_result_expires,
    # ── Queue routing ─────────────────────────────────────────────────────────
    task_routes={
        "app.workers.upload_pipeline.parse_document_task": {"queue": "ingestion"},
        "app.workers.cleanup_pipeline.delete_document_task": {"queue": "cleanup"},
        "app.workers.cleanup_pipeline.cleanup_old_chat_sessions_task": {"queue": "cleanup"},
    },
    task_default_queue="default",
    # ── Serialization ─────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # ── Beat schedule (periodic tasks) ────────────────────────────────────────
    beat_schedule={
        "cleanup-old-chat-sessions": {
            "task": "app.workers.cleanup_pipeline.cleanup_old_chat_sessions_task",
            "schedule": 86400.0,  # Every 24 hours
        },
    },
)
