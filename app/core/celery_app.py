"""
Celery application configuration.

Reliability settings (most important):
  - task_acks_late=True: ACK task AFTER completion, not when received.
    If the worker crashes mid-task, the broker re-queues it automatically.
  - task_reject_on_worker_lost=True: Explicit requeue on unexpected worker death.
  - worker_prefetch_multiplier=1: Each worker holds exactly 1 task at a time.
    Docling + EasyOCR tasks are heavy; hoarding multiple tasks wastes memory
    and causes unfair load distribution.

Time limits (prevent hung parse tasks):
  - task_soft_time_limit: Raises SoftTimeLimitExceeded → worker catches it,
    updates document status to 'failed', then exits gracefully.
  - task_time_limit: Hard kill after this; should be > soft limit.
"""

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "chatbot_rag",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker"],
)

celery_app.conf.update(
    # ── Reliability ───────────────────────────────────────────────────────────
    task_acks_late=True,               # ACK after task completes, not when received
    task_reject_on_worker_lost=True,   # Requeue if worker dies mid-task

    # ── Performance ───────────────────────────────────────────────────────────
    worker_prefetch_multiplier=1,      # 1 task per worker — fair distribution

    # ── Time limits (Docling + EasyOCR can be slow on large PDFs) ────────────
    task_time_limit=1800,              # 30 min hard kill
    task_soft_time_limit=1500,         # 25 min → SoftTimeLimitExceeded in worker

    # ── Queue routing ─────────────────────────────────────────────────────────
    task_routes={
        "app.worker.parse_document_task":   {"queue": "ingestion"},
        "app.worker.delete_document_task":  {"queue": "cleanup"},
    },
    task_default_queue="default",

    # ── Serialization ─────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
