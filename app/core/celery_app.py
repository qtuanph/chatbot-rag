from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "chatbot_rag",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker"],
)

celery_app.conf.task_default_queue = "default"
