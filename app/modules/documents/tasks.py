"""
Celery task definitions for document upload and ingestion pipeline.
Uses SYNCHRONOUS Redis for status updates to ensure 100% stability.
"""

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.modules.documents.repositories import DocumentRepository, SectionRepository
from app.adapters.storage import build_storage
from app.modules.documents.ingestion.ingestion_service import IngestionService
from app.adapters.parsers.llamaparse_adapter import LlamaParseParser
from app.core.redis import get_redis_client
from app.utils.audit import safe_record_audit
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _verify_ingestion(document_id: str, storage) -> dict:
    uri = f"s3://{settings.s3_bucket}/{document_id}/ocr_output.md"
    file_exists = await asyncio.to_thread(storage.file_exists, uri)
    return {"storage_exists": file_exists, "passed": file_exists}


@celery_app.task(
    name="app.workers.upload_tasks.parse_document_task",
    bind=True,
    acks_late=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=settings.celery_retry_backoff,
    max_retries=settings.celery_max_retries,
    soft_time_limit=settings.celery_task_soft_time_limit,
    time_limit=settings.celery_task_time_limit,
)
def parse_document_task(self, task_id: str, document_id: str, file_path: str, user_id: str | None = None) -> dict:
    storage = build_storage()
    filename = file_path.split("/")[-1]

    async def _run_async_pipeline():
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)

            await doc_repo.update_status(
                document_id,
                status="processing",
                stage="initializing",
                progress_percent=5,
                status_message="[1/4] Đang khởi tạo môi trường nạp liệu...",
            )

            async_redis = get_redis_client()
            try:
                content = await asyncio.to_thread(storage.download_bytes, file_path)
                section_repo = SectionRepository(session)

                pipeline = IngestionService(
                    redis_client=async_redis,
                    db_session=session,
                    section_repo=section_repo,
                )

                async def _progress_callback(stage: str, percent: int, message: str = ""):
                    logger.info("[%s] Progress: %d%% - %s", document_id, percent, message)
                    try:
                        async with AsyncSessionLocal() as fresh_session:
                            fresh_repo = DocumentRepository(fresh_session)
                            await fresh_repo.update_status(
                                document_id,
                                status="processing",
                                stage=stage,
                                progress_percent=percent,
                                status_message=message,
                            )
                    except Exception as status_err:
                        logger.warning("[%s] Failed to update progress in DB: %s", document_id, status_err)

                ingestion_result = await pipeline.ingest(
                    filename=filename,
                    content=content,
                    user_id=user_id or "system",
                    document_id=document_id,
                    progress_callback=_progress_callback,
                )

                verify = await _verify_ingestion(document_id, storage)

                if ingestion_result.parse_metadata and ingestion_result.parse_metadata.sections_data:
                    for sec in ingestion_result.parse_metadata.sections_data:
                        title = sec.get("title", "")
                        if title and title not in ("Untitled",) and not title.startswith("Phan "):
                            if title != filename:
                                await doc_repo.update_title(document_id, title)
                            break

                if ingestion_result.success:
                    artifact_dict = ingestion_result.parse_metadata.to_dict() if ingestion_result.parse_metadata else {}
                    artifact_dict["verification"] = verify
                    await doc_repo.finalize_ingestion(
                        document_id,
                        artifact_dict=artifact_dict,
                        node_count=ingestion_result.node_count,
                        total_text_chars=ingestion_result.total_text_chars,
                        progress_percent=100,
                    )
                else:
                    raise ValueError(f"Ingestion failed: {', '.join(ingestion_result.errors)}")

                return ingestion_result

            except Exception as e:
                error_msg = str(e)
                if len(error_msg) > 480:
                    error_msg = error_msg[:480] + "..."
                await doc_repo.update_status(
                    document_id,
                    status="failed",
                    stage="failed",
                    status_message=f"Loi: {error_msg}",
                )
                raise e
            finally:
                await async_redis.aclose()

    try:
        result = asyncio.run(_run_async_pipeline())

        safe_record_audit(
            action="document.ingestion_complete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details={"node_count": result.node_count},
        )

        return {"status": "success", "document_id": document_id}

    except Exception as e:
        logger.error("[%s] Sync wrapper caught error: %s", document_id, e)
        safe_record_audit(
            action="document.ingestion_failed",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details={"error": str(e)},
        )
        raise e


@celery_app.task(
    name="app.workers.upload_tasks.rechunk_document_task",
    bind=True,
    acks_late=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=settings.celery_retry_backoff,
    max_retries=settings.celery_max_retries,
    soft_time_limit=settings.celery_task_soft_time_limit,
    time_limit=settings.celery_task_time_limit,
)
def rechunk_document_task(self, task_id: str, document_id: str, user_id: str | None = None) -> dict:
    storage = build_storage()
    ocr_uri = f"s3://{settings.s3_bucket}/{document_id}/ocr_output.md"

    async def _rechunk_progress(stage: str, percent: int, message: str = ""):
        try:
            async with AsyncSessionLocal() as fresh_session:
                await DocumentRepository(fresh_session).update_status(
                    document_id,
                    status="processing",
                    stage=stage,
                    progress_percent=percent,
                    status_message=message,
                )
        except Exception as status_err:
            logger.warning("[%s] Status update failed: %s", document_id, status_err)

    async def _run_async():
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)
            section_repo = SectionRepository(session)

            await _rechunk_progress("rechunking", 5, "[1/4] Đang đọc OCR markdown từ S3...")

            async_redis = get_redis_client()
            try:
                md_bytes = await asyncio.to_thread(storage.download_bytes, ocr_uri)
                markdown_text = md_bytes.decode("utf-8")
                logger.info("[%s] Loaded %d bytes of OCR markdown from S3", document_id, len(md_bytes))

                await _rechunk_progress("rechunking", 15, "[2/4] Đang chia lại node từ markdown...")

                nodes, sections_data = LlamaParseParser.parse_from_markdown(
                    markdown_text, document_id, source_format="markdown"
                )
                logger.info(
                    "[%s] Local parsing produced %d nodes, %d sections", document_id, len(nodes), len(sections_data)
                )

                await _rechunk_progress("rechunking", 25, "[2/4] Đang dọn dẹp dữ liệu cũ...")

                try:
                    from app.core.llama_index import get_vector_store

                    vs = get_vector_store()
                    await vs.adelete(ref_doc_id=document_id)
                    await section_repo.delete_sections(document_id)
                    logger.info("[%s] Cleaned old vectors and sections", document_id)
                except Exception as clean_err:
                    logger.warning("[%s] Partial cleanup error: %s", document_id, clean_err)

                await _rechunk_progress("rechunking", 35, "[3/4] Đang lưu sections vào DB...")
                await section_repo.store_sections(document_id, sections_data)

                await _rechunk_progress("rechunking", 40, "[4/4] Đang embedding và index vào Qdrant...")

                from app.modules.documents.ingestion.pipeline import run_ingestion_pipeline

                async def _on_rechunk_pipeline_progress(processed_docs: int, total_docs: int, total_stored: int):
                    if total_docs <= 0:
                        return
                    percent = 40 + int((95 - 40) * (processed_docs / total_docs))
                    await _rechunk_progress(
                        "rechunking",
                        min(95, max(40, percent)),
                        f"[4/4] Đã embed {processed_docs}/{total_docs} chunk, đang ghi vector vào Qdrant...",
                    )

                stored = await run_ingestion_pipeline(
                    nodes,
                    document_id,
                    sections_data,
                    progress_callback=_on_rechunk_pipeline_progress,
                )
                logger.info("[%s] Rechunk complete: %d nodes stored in Qdrant", document_id, stored)

                for sec in sections_data:
                    title = sec.get("title", "")
                    if title and title not in ("Untitled",) and not title.startswith("Phan "):
                        await doc_repo.update_title(document_id, title)
                        break

                await doc_repo.finalize_ingestion(
                    document_id,
                    artifact_dict={
                        "rechunk": True,
                        "source": "ocr_output.md",
                        "node_count": stored,
                        "section_count": len(sections_data),
                    },
                    node_count=stored,
                    total_text_chars=sum(len(n.text) for n in nodes),
                    progress_percent=100,
                )

                return {"node_count": stored, "section_count": len(sections_data)}

            except Exception as e:
                logger.error("[%s] Rechunk failed: %s", document_id, e)
                try:
                    async with AsyncSessionLocal() as fail_session:
                        await DocumentRepository(fail_session).update_status(
                            document_id,
                            status="failed",
                            stage="failed",
                            status_message=f"Rechunk loi: {str(e)}",
                        )
                except Exception:
                    pass
                raise e
            finally:
                await async_redis.aclose()

    try:
        result = asyncio.run(_run_async())
        safe_record_audit(
            action="document.rechunk_complete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details=result,
        )
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        logger.error("[%s] Rechunk sync wrapper error: %s", document_id, e)
        safe_record_audit(
            action="document.rechunk_failed",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details={"error": str(e)},
        )
        raise e
