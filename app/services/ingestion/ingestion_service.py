"""
Ingestion Pipeline: Main orchestration for document parsing → hierarchy → embedding → storage.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import TYPE_CHECKING, Callable, Any
from dataclasses import dataclass, field

from app.adapters.base import IngestedNode, ParsingMetadata
from app.adapters.parsers.docling import DoclingParser
from app.utils.hierarchy_validator import HierarchyValidator, ValidationReport
from app.utils.text_refiner import rule_based_refiner
from app.core.config import settings
from app.repositories.section_repository import SectionRepository
from app.core.hardware import hardware

if TYPE_CHECKING:
    from app.adapters.base import BaseEmbedding, BaseVectorStore
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of ingestion pipeline."""

    success: bool
    document_id: str
    node_count: int
    total_text_chars: int
    parse_metadata: ParsingMetadata | None
    validation_report: ValidationReport | None
    storage_ids: list[str]
    section_count: int = 0  # Number of sections stored in PostgreSQL
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


# Type alias for clarity
ProgressCallback = Callable[[str, int, str], Any]  # Should be awaited if async


class IngestionService:
    """
    Main ingestion orchestration (Async):
    1. Parse document (Docling + PaddleOCR)
    2. Validate hierarchy
    3. Embed + store nodes in chunks (Async-parallel embedding, incremental Qdrant writes)
    4. Report progress at each chunk via optional callback
    """

    def __init__(
        self,
        redis_client: Any,
        embedding_service: BaseEmbedding | None = None,
        vector_store: BaseVectorStore | None = None,
        db_session: AsyncSession | None = None,
        section_repo: SectionRepository | None = None,
    ):
        self.redis = redis_client
        self.parser = DoclingParser()
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.db_session = db_session
        self.section_repo = section_repo
        self.validator = HierarchyValidator()

    async def ingest(
        self,
        filename: str,
        content: bytes,
        user_id: str,
        document_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestionResult:
        """
        Asynchronous ingestion pipeline with chunked embed+store and progress reporting.
        """
        start_time = time.time()
        errors: list[str] = []
        warnings: list[str] = []
        nodes: list[IngestedNode] = []
        parse_metadata = None
        validation_report = None
        storage_ids: list[str] = []
        section_count = 0
        async def _cb(stage: str, percent: int, message: str = "") -> None:
            if progress_callback:
                try:
                    await asyncio.to_thread(progress_callback, stage, percent, message)
                except Exception as cb_exc:
                    logger.warning("[%s] Progress callback error: %s", document_id, cb_exc)

        try:
            # ── Step 1: Parse ────────────────────────────────────────────────
            logger.info("[%s] Starting ingestion: %s", document_id, filename)
            await _cb("parsing", 5, f"Parsing {filename}…")

            nodes, parse_metadata = await self.parser.parse(filename, content, document_id=document_id)

            # ── Step 1.5: Text Refinement (Sanitize & Clean OCR Artifacts) ───
            nodes = await asyncio.to_thread(rule_based_refiner.refine_nodes, nodes)
            await _cb("parsing", 32, "Refining extracted text...")
            sections_data = getattr(parse_metadata, "sections_data", None) or []
            if sections_data:
                sections_data = await asyncio.to_thread(rule_based_refiner.refine_sections, sections_data)
                parse_metadata.sections_data = sections_data

            # ── Step 2: Validate hierarchy (wrapped in to_thread as it's CPU-intensive)
            await _cb("parsing", 35, "Validating document structure…")
            validation_report = await asyncio.to_thread(self.validator.validate, nodes)
            if not validation_report.is_valid:
                errors.extend(validation_report.errors)
                warnings.extend(validation_report.warnings)
            else:
                logger.info("[%s] Hierarchy valid (depth=%s)", document_id, validation_report.depth)

            # ── Step 2.5: Store Sections ─────────────────────────────────────
            section_count = 0
            sections_data = getattr(parse_metadata, "sections_data", None) or []
            if sections_data and self.db_session:
                await _cb("parsing", 37, f"Storing {len(sections_data)} sections…")
                section_repo = self.section_repo or SectionRepository(self.db_session)
                section_ids = await section_repo.store_sections(document_id, sections_data)
                section_count = len(section_ids)

                # Enrich nodes with section context
                section_map = {s["section_id"]: s for s in sections_data}
                for node in nodes:
                    sec_id = node.metadata.get("section_id")
                    if sec_id and sec_id in section_map:
                        sec = section_map[sec_id]
                        node.metadata["section_content"] = sec.get("content", "")
                        node.metadata["breadcrumb"] = sec.get("breadcrumb", [])
                        node.metadata["level"] = sec.get("level", 0)

            # ── Step 2.6: Contextual Enrichment ─────────────────────────────
            await _cb("parsing", 39, "Enriching chunks with document context…")
            from app.utils.contextualizer import Contextualizer

            contextualizer = Contextualizer()
            nodes = await asyncio.to_thread(contextualizer.contextualize, filename, nodes)

            # ── Step 3: Embed + Store ────────────────────────────────────────
            n_chunks = 0
            if self.embedding_service and nodes:
                chunk_size = settings.ingestion_embedding_chunk_size
                n_chunks = math.ceil(len(nodes) / chunk_size) or 1

                # BM25 sparse encoder (Using Injected Redis for Consistency)
                from app.utils.bm25_index import get_async_bm25_encoder

                bm25_encoder = await get_async_bm25_encoder(self.redis)

                # Semaphore to control concurrency (limit VRAM pressure)
                concurrency = settings.ingestion_embed_parallelism or hardware.embed_parallelism
                concurrency = max(1, min(concurrency, 4))
                semaphore = asyncio.Semaphore(concurrency)

                async def _process_chunk(chunk_idx: int, chunk_nodes: list[IngestedNode]):
                    async with semaphore:
                        try:
                            chunk_texts = [n.text for n in chunk_nodes]
                            vecs = await self.embedding_service.embed_batch(chunk_texts)

                            if self.vector_store:
                                sparse_embs = await asyncio.to_thread(
                                    bm25_encoder.encode_batch_sparse_vectors, chunk_texts
                                )
                                ids = await self.vector_store.store(
                                    document_id,
                                    chunk_nodes,
                                    vecs,
                                    sparse_embeddings=sparse_embs,
                                )
                                storage_ids.extend(ids)

                            pct = 40 + int(50 * (chunk_idx + 1) / n_chunks)
                            await _cb("embedding", pct, f"Indexing section {chunk_idx + 1}/{n_chunks}…")
                            logger.info("[%s] Chunk %d/%d processed", document_id, chunk_idx + 1, n_chunks)
                        except Exception as e:
                            logger.error("[%s] Chunk %d/%d failed: %s", document_id, chunk_idx + 1, n_chunks, e)
                            errors.append(f"Chunk {chunk_idx + 1} failed: {str(e)}")

                tasks = []
                for idx, start in enumerate(range(0, len(nodes), chunk_size)):
                    chunk = nodes[start : start + chunk_size]
                    tasks.append(_process_chunk(idx, chunk))

                await asyncio.gather(*tasks)

                # Save BM25 vocabulary back to Redis after ingestion
                await bm25_encoder.save_async()

            duration_ms = (time.time() - start_time) * 1000

            # Success check (threshold logic)
            error_threshold = max(1, int(n_chunks * 0.5)) if n_chunks > 0 else 1
            has_critical_failure = len(errors) > error_threshold

            if has_critical_failure:
                _cb("failed", 0, f"{len(errors)} chunk errors exceeded threshold")
                if self.db_session and section_count > 0:
                    section_repo = self.section_repo or SectionRepository(self.db_session)
                    await section_repo.delete_sections(document_id)
                    section_count = 0
            else:
                await _cb("ready", 100, "Ingestion complete")

            return IngestionResult(
                success=not has_critical_failure,
                document_id=document_id,
                node_count=len(nodes),
                total_text_chars=sum(len(n.text) for n in nodes),
                parse_metadata=parse_metadata,
                validation_report=validation_report,
                storage_ids=storage_ids,
                section_count=section_count,
                errors=errors,
                warnings=warnings,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("[%s] Ingestion failed: %s", document_id, e)
            _cb("failed", 0, str(e))
            return IngestionResult(
                success=False,
                document_id=document_id,
                node_count=len(nodes),
                total_text_chars=0,
                parse_metadata=parse_metadata,
                validation_report=validation_report,
                storage_ids=[],
                section_count=0,
                errors=[str(e)] + errors,
                warnings=warnings,
                duration_ms=duration_ms,
            )
