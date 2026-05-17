"""
Celery application configuration.

Reliability settings (most important):
  - task_acks_late=True: ACK task AFTER completion, not when received.
    If the worker crashes mid-task, the broker re-queues it automatically.
  - task_reject_on_worker_lost=True: Explicit requeue on unexpected worker death.
  - worker_prefetch_multiplier=1: Each worker holds exactly 1 task at a time.
    Docling + EasyOCR tasks are heavy; hoarding multiple tasks wastes memory
    and causes unfair load distribution.

Memory safety:
  - worker_max_memory_per_child=1.5GB: Kill child process if RSS exceeds limit.
    Prevents memory leaks from large PDF processing accumulating over time.

Broker reliability:
  - visibility_timeout=7200s: Redis re-delivery guard — tasks running >2h
    are assumed lost. Longest expected task is OCR/parse (~30 min).
  - broker_connection_retry_on_startup=True: Don't crash if Redis unavailable.

Queue routing:
  - ingestion: workers (GPU-bound embedding tasks)
  - cleanup: workers (lightweight delete + beat tasks)
  - default: fallback queue (chat message saves, etc.)

Time limits (prevent hung parse tasks):
  - task_soft_time_limit: Raises SoftTimeLimitExceeded → worker catches it,
    updates document status to 'failed', then exits gracefully.
  - task_time_limit: Hard kill after this; should be > soft limit.
"""

from celery import Celery

from app.core.config import settings

_ALL_MODULES = [
    "app.modules.documents.tasks",
    "app.modules.documents.cleanup_tasks",
    "app.modules.chat.tasks",
    "app.modules.system.tasks",
    "app.modules.analytics.audit_worker",
]

celery_app = Celery(
    "chatbot_rag",
    broker=settings.celery_broker_url_auth,
    backend=settings.celery_result_backend_auth,
    include=_ALL_MODULES,
)

celery_app.conf.update(
    # ── Broker URL (explicit override — Celery auto-reads CELERY_BROKER_URL env var without password) ──
    broker_url=settings.celery_broker_url_auth,
    result_backend=settings.celery_result_backend_auth,
    # ── Reliability ───────────────────────────────────────────────────────────
    task_acks_late=True,  # ACK after task completes, not when received
    task_reject_on_worker_lost=True,  # Requeue if worker dies mid-task
    # ── Performance ───────────────────────────────────────────────────────────
    worker_prefetch_multiplier=1,  # 1 task per worker — fair distribution
    worker_disable_rate_limits=True,  # Rate limit at API level, not Celery
    # ── Memory safety ─────────────────────────────────────────────────────────
    worker_max_memory_per_child=settings.celery_worker_max_memory_kb,
    # ── Time limits (Docling + EasyOCR can be slow on large PDFs) ────────────
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
        "app.workers.upload_tasks.parse_document_task": {"queue": "ingestion"},
        "app.workers.cleanup_tasks.delete_document_task": {"queue": "cleanup"},
        "app.workers.cleanup_tasks.cleanup_old_chat_sessions_task": {"queue": "cleanup"},
        "app.workers.chat_tasks.save_chat_message_task": {"queue": "default"},
        "app.workers.maintenance_tasks.rebuild_bm25_index_task": {"queue": "ingestion"},
        "app.workers.maintenance_tasks.cleanup_orphaned_vectors_task": {"queue": "cleanup"},
        "app.workers.audit_worker.process_audit_stream": {"queue": "default"},
        "app.workers.memory_tasks.extract_memories_task": {"queue": "default"},
    },
    task_default_queue="default",
    # ── Serialization ─────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # ── Beat schedule (periodic tasks) ────────────────────────────────────────
    beat_schedule={
        "cleanup-old-chat-sessions": {
            "task": "app.workers.cleanup_tasks.cleanup_old_chat_sessions_task",
            "schedule": settings.chat_session_ttl_days * 86400.0,
        },
        "cleanup-orphaned-vectors": {
            "task": "app.workers.maintenance_tasks.cleanup_orphaned_vectors_task",
            "schedule": settings.chat_session_ttl_days * 86400.0,
        },
        "process-audit-stream": {
            "task": "app.workers.audit_worker.process_audit_stream",
            "schedule": settings.audit_stream_process_interval,
            "args": (settings.audit_stream_batch_size,),
        },
    },
)
