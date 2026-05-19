"""
Celery task definitions for document upload and ingestion pipeline.
Uses SYNCHRONOUS Redis for status updates to ensure 100% stability.
"""

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.modules.documents.repositories import DocumentRepository, SectionRepository
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.adapters.storage import build_storage
from app.modules.documents.ingestion.ingestion_service import IngestionService
from app.adapters.parsers.llamaparse_adapter import LlamaParseParser
from app.modules.documents.ingestion.llama_pipeline import LlamaIngestionPipeline
from app.core.redis import get_sync_redis_client, get_redis_client
from app.modules.documents.utils.document_registry import DocumentRegistry
from app.utils.audit import safe_record_audit
from app.modules.system.tasks import rebuild_bm25_index_task
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


def _build_vector_store(embedding_service) -> QdrantVectorStore:
    """Build a QdrantVectorStore instance."""
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size,
        timeout=settings.qdrant_timeout,
    )


async def _verify_ingestion(
    document_id: str,
    file_path: str,
    vector_store: QdrantVectorStore,
    storage,
) -> dict:
    """Post-ingestion verification (Async)."""
    qdrant_count = await vector_store.count(document_id)
    file_exists = await asyncio.to_thread(storage.file_exists, file_path)
    return {
        "qdrant_count": qdrant_count,
        "storage_exists": file_exists,
        "passed": qdrant_count > 0 and file_exists,
    }


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
    """
    Ingestion task with Synchronous status management for reliability.
    """
    # 1. Initialize Sync Resources
    sync_redis = get_sync_redis_client()
    registry = DocumentRegistry(sync_redis)
    storage = build_storage()
    filename = file_path.split("/")[-1]

    # 2. Local Async Execution Block
    async def _run_async_pipeline():
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)

            # Update status to processing
            await doc_repo.update_status(
                document_id,
                status="processing",
                stage="initializing",
                progress_percent=5,
                status_message="[1/4] Đang khởi tạo môi trường nạp liệu...",
            )

            # Create an isolated async redis client for the pipeline (Loop-safe)
            async_redis = get_redis_client()
            try:
                content = await asyncio.to_thread(storage.download_bytes, file_path)
                embedding_service = build_embedding_service()
                vector_store = _build_vector_store(embedding_service)
                section_repo = SectionRepository(session)

                pipeline = IngestionService(
                    redis_client=async_redis,
                    embedding_service=embedding_service,
                    vector_store=vector_store,
                    db_session=session,
                    section_repo=section_repo,
                )

                async def _progress_callback(stage: str, percent: int, message: str = ""):
                    """Async callback to update DB status using a fresh session for 100% stability."""
                    logger.info("[%s] Progress: %d%% - %s", document_id, percent, message)
                    try:
                        # Use a fresh session for each update to avoid transaction sharing issues
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

                # Core Ingestion (The only truly async part)
                ingestion_result = await pipeline.ingest(
                    filename=filename,
                    content=content,
                    user_id=user_id or "system",
                    document_id=document_id,
                    progress_callback=_progress_callback,
                )

                # Verification
                verify = await _verify_ingestion(document_id, file_path, vector_store, storage)

                # Finalize DB
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
                await doc_repo.update_status(
                    document_id,
                    status="failed",
                    stage="failed",
                    status_message=f"Lỗi: {str(e)}",
                )
                raise e
            finally:
                await async_redis.aclose()

    # 3. Execute Async Pipeline
    try:
        result = asyncio.run(_run_async_pipeline())

        # 4. Sync Finalization (Safe from loop errors)
        registry.purge_sync(document_id)
        registry.invalidate_active_ids_sync()

        # Audit (Truly sync call now)
        safe_record_audit(
            action="document.ingestion_complete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details={"node_count": result.node_count},
        )

        # Trigger maintenance
        rebuild_bm25_index_task.delay()

        return {"status": "success", "document_id": document_id}

    except Exception as e:
        logger.error("[%s] Sync wrapper caught error: %s", document_id, e)
        # Audit failure (Truly sync call now)
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
    """Re-chunk document from saved OCR markdown without calling LlamaParse API."""
    sync_redis = get_sync_redis_client()
    registry = DocumentRegistry(sync_redis)
    storage = build_storage()
    ocr_uri = f"s3://{settings.s3_bucket}/{document_id}/ocr_output.md"

    async def _rechunk_progress(stage: str, percent: int, message: str = ""):
        """Update status using a fresh session to avoid transaction conflicts."""
        try:
            async with AsyncSessionLocal() as fresh_session:
                await DocumentRepository(fresh_session).update_status(
                    document_id, status="processing", stage=stage, progress_percent=percent, status_message=message
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

                embedding_service = build_embedding_service()
                vector_store = _build_vector_store(embedding_service)

                await _rechunk_progress("rechunking", 25, "[2/4] Đang dọn dẹp dữ liệu cũ...")

                try:
                    await vector_store.delete(document_id)
                    await section_repo.delete_sections(document_id)
                    logger.info("[%s] Cleaned old vectors and sections", document_id)
                except Exception as clean_err:
                    logger.warning("[%s] Partial cleanup error: %s", document_id, clean_err)

                # Run LlamaIndex pipeline
                pipeline = LlamaIngestionPipeline()
                llm_docs = []
                for n in nodes:
                    from llama_index.core.schema import Document as LlamaDocument

                    llm_docs.append(
                        LlamaDocument(
                            text=n.text,
                            metadata={
                                "node_id": n.node_id,
                                "document_id": n.document_id,
                                "page_number": n.page_number,
                                "section_title": n.section_title,
                                "parent_id": n.parent_id,
                                "order": n.order,
                                **n.metadata,
                            },
                        )
                    )

                llama_nodes = await pipeline.arun(llm_docs)
                ctx_nodes = pipeline.convert_ingested_nodes(llama_nodes, document_id, "markdown")
                logger.info("[%s] Pipeline produced %d nodes for indexing", document_id, len(ctx_nodes))

                await _rechunk_progress("rechunking", 35, "[3/4] Đang lưu sections vào DB...")

                await section_repo.store_sections(document_id, sections_data)
                section_map = {s["section_id"]: s for s in sections_data}
                for node in ctx_nodes:
                    sec_id = node.metadata.get("section_id")
                    if sec_id and sec_id in section_map:
                        sec = section_map[sec_id]
                        node.metadata["section_content"] = sec.get("content", "")
                        node.metadata["breadcrumb"] = sec.get("breadcrumb", [])
                        node.metadata["level"] = sec.get("level", 0)

                await _rechunk_progress("rechunking", 40, "[4/4] Đang embedding và index vào Qdrant...")
                t0 = time.time()

                from app.modules.documents.utils import get_async_bm25_encoder

                bm25_encoder = await get_async_bm25_encoder(async_redis)
                t1 = time.time()
                logger.info("[%s] BM25 encoder ready in %.1fs", document_id, t1 - t0)

                chunk_size = settings.ingestion_embedding_chunk_size
                n_chunks = max(1, (len(ctx_nodes) + chunk_size - 1) // chunk_size)
                from app.core.hardware import hardware

                concurrency = max(1, min(settings.ingestion_embed_parallelism or hardware.embed_parallelism, 4))
                semaphore = asyncio.Semaphore(concurrency)
                t2 = time.time()
                logger.info(
                    "[%s] Setup %d chunks, concurrency=%d in %.1fs", document_id, n_chunks, concurrency, t2 - t1
                )

                async def _process_chunk(chunk_idx: int, chunk_nodes: list):
                    async with semaphore:
                        ct0 = time.time()
                        texts = [n.text for n in chunk_nodes]
                        vecs = await embedding_service.embed_batch(texts)
                        ct1 = time.time()
                        sparse_embs = await asyncio.to_thread(bm25_encoder.encode_batch_sparse_vectors, texts)
                        await vector_store.store(document_id, chunk_nodes, vecs, sparse_embeddings=sparse_embs)
                        ct2 = time.time()
                        logger.info(
                            "[%s] Batch %d/%d: embed=%.1fs, store=%.1fs",
                            document_id,
                            chunk_idx + 1,
                            n_chunks,
                            ct1 - ct0,
                            ct2 - ct1,
                        )
                        pct = 40 + int(55 * (chunk_idx + 1) / n_chunks)
                        await _rechunk_progress(
                            "rechunking", pct, f"[4/4] Indexing: batch {chunk_idx + 1}/{n_chunks}..."
                        )

                tasks = []
                for idx in range(n_chunks):
                    start = idx * chunk_size
                    end = start + chunk_size
                    tasks.append(_process_chunk(idx, ctx_nodes[start:end]))

                await asyncio.gather(*tasks)
                await bm25_encoder.save_async()

                qdrant_count = await vector_store.count(document_id)
                logger.info(
                    "[%s] Rechunk complete: %d nodes, %d Qdrant vectors", document_id, len(ctx_nodes), qdrant_count
                )

                await doc_repo.finalize_ingestion(
                    document_id,
                    artifact_dict={
                        "rechunk": True,
                        "source": "ocr_output.md",
                        "node_count": len(ctx_nodes),
                        "section_count": len(sections_data),
                        "qdrant_count": qdrant_count,
                    },
                    node_count=len(ctx_nodes),
                    total_text_chars=sum(len(n.text) for n in ctx_nodes),
                    progress_percent=100,
                )

                return {"node_count": len(ctx_nodes), "section_count": len(sections_data), "qdrant_count": qdrant_count}

            except Exception as e:
                logger.error("[%s] Rechunk failed: %s", document_id, e)
                try:
                    async with AsyncSessionLocal() as fail_session:
                        await DocumentRepository(fail_session).update_status(
                            document_id,
                            status="failed",
                            stage="failed",
                            status_message=f"Rechunk lỗi: {str(e)}",
                        )
                except Exception:
                    pass
                raise e
            finally:
                await async_redis.aclose()

    try:
        result = asyncio.run(_run_async())
        registry.purge_sync(document_id)
        registry.invalidate_active_ids_sync()
        safe_record_audit(
            action="document.rechunk_complete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            details=result,
        )
        rebuild_bm25_index_task.delay()
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
