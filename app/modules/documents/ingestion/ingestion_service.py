"""
Ingestion Pipeline: Orchestrates document parsing, hierarchy validation, enrichment, and vector indexing.
Uses a Step-based Pipeline pattern for maintainability and granular status reporting.
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
from app.modules.documents.section_repository import SectionRepository
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
    section_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class PipelineContext:
    """Shared state between pipeline steps."""

    filename: str
    content: bytes
    document_id: str
    user_id: str
    nodes: list[IngestedNode] = field(default_factory=list)
    parse_metadata: ParsingMetadata | None = None
    validation_report: ValidationReport | None = None
    storage_ids: list[str] = field(default_factory=list)
    section_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)


ProgressCallback = Callable[[str, int, str], Any]


class IngestionService:
    """
    Main ingestion orchestration using Pipeline Pattern.
    Each major operation is a 'Step' for better maintainability and status tracking.
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
        """Main entry point for ingestion."""
        ctx = PipelineContext(filename, content, document_id, user_id)

        async def report(stage: str, percent: int, message: str = "") -> None:
            if progress_callback:
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(stage, percent, message)
                    else:
                        await asyncio.to_thread(progress_callback, stage, percent, message)
                except Exception as cb_exc:
                    logger.warning("[%s] Progress callback error: %s", document_id, cb_exc)

        try:
            # ── Step 1: Parse & Refine ──
            await self._parse_step(ctx, report)

            # ── Step 2: Validate ──
            await self._validate_step(ctx, report)

            # ── Step 3: Store Sections ──
            await self._store_sections_step(ctx, report)

            # ── Step 4: Contextualize ──
            await self._enrich_step(ctx, report)

            # ── Step 5: Embed & Index ──
            await self._vector_index_step(ctx, report)

            duration_ms = (time.time() - ctx.start_time) * 1000

            # Success logic (re-used threshold from original code)
            n_nodes = len(ctx.nodes)
            error_threshold = max(1, int(n_nodes * 0.5 / settings.ingestion_embedding_chunk_size)) if n_nodes > 0 else 1
            has_critical_failure = len(ctx.errors) > error_threshold

            if has_critical_failure:
                await report("failed", 0, f"{len(ctx.errors)} chunk errors exceeded threshold")
            else:
                await report("ready", 100, "Ingestion complete")

            return IngestionResult(
                success=not has_critical_failure,
                document_id=ctx.document_id,
                node_count=len(ctx.nodes),
                total_text_chars=sum(len(n.text) for n in ctx.nodes),
                parse_metadata=ctx.parse_metadata,
                validation_report=ctx.validation_report,
                storage_ids=ctx.storage_ids,
                section_count=ctx.section_count,
                errors=ctx.errors,
                warnings=ctx.warnings,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error("[%s] Ingestion pipeline crashed: %s", document_id, e, exc_info=True)
            await report("failed", 0, str(e))
            return IngestionResult(
                success=False,
                document_id=document_id,
                node_count=len(ctx.nodes),
                total_text_chars=0,
                parse_metadata=ctx.parse_metadata,
                validation_report=ctx.validation_report,
                storage_ids=[],
                section_count=0,
                errors=[str(e)] + ctx.errors,
                warnings=ctx.warnings,
                duration_ms=(time.time() - ctx.start_time) * 1000,
            )

    # ── Pipeline Steps ──────────────────────────────────────────────────

    async def _parse_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Parse document and refine text."""
        await report("parsing", 5, f"Parsing {ctx.filename} using Docling...")
        nodes, metadata = await self.parser.parse(ctx.filename, ctx.content, document_id=ctx.document_id)

        await report("parsing", 25, "Cleaning and refining extracted text...")
        ctx.nodes = await asyncio.to_thread(rule_based_refiner.refine_nodes, nodes)

        sections_data = getattr(metadata, "sections_data", None) or []
        if sections_data:
            sections_data = await asyncio.to_thread(rule_based_refiner.refine_sections, sections_data)
            metadata.sections_data = sections_data

        ctx.parse_metadata = metadata

    async def _validate_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Validate hierarchy structure."""
        await report("parsing", 35, "Validating document hierarchy...")
        report_data = await asyncio.to_thread(self.validator.validate, ctx.nodes)
        ctx.validation_report = report_data

        if not report_data.is_valid:
            ctx.errors.extend(report_data.errors)
            ctx.warnings.extend(report_data.warnings)
        else:
            logger.info("[%s] Hierarchy validated: depth=%d", ctx.document_id, report_data.depth)

    async def _store_sections_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Store sections in DB and enrich nodes."""
        sections_data = getattr(ctx.parse_metadata, "sections_data", None) or []
        if not sections_data or not self.db_session:
            return

        await report("parsing", 37, f"Saving {len(sections_data)} sections to database...")
        repo = self.section_repo or SectionRepository(self.db_session)
        section_ids = await repo.store_sections(ctx.document_id, sections_data)
        ctx.section_count = len(section_ids)

        # Enrich nodes with section context (moved from monolithic ingest)
        section_map = {s["section_id"]: s for s in sections_data}
        for node in ctx.nodes:
            sec_id = node.metadata.get("section_id")
            if sec_id and sec_id in section_map:
                sec = section_map[sec_id]
                node.metadata["section_content"] = sec.get("content", "")
                node.metadata["breadcrumb"] = sec.get("breadcrumb", [])
                node.metadata["level"] = sec.get("level", 0)

    async def _enrich_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Contextual enrichment for chunks."""
        await report("parsing", 39, "Enriching chunks with document-level context...")
        from app.utils.contextualizer import Contextualizer

        contextualizer = Contextualizer()
        ctx.nodes = await asyncio.to_thread(contextualizer.contextualize, ctx.filename, ctx.nodes)

    async def _vector_index_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Embedding and Vector storage indexing."""
        if not self.embedding_service or not ctx.nodes:
            return

        chunk_size = settings.ingestion_embedding_chunk_size
        n_chunks = math.ceil(len(ctx.nodes) / chunk_size) or 1

        from app.utils.bm25_index import get_async_bm25_encoder

        bm25_encoder = await get_async_bm25_encoder(self.redis)

        concurrency = max(1, min(settings.ingestion_embed_parallelism or hardware.embed_parallelism, 4))
        semaphore = asyncio.Semaphore(concurrency)

        async def _process(chunk_idx: int, chunk_nodes: list[IngestedNode]):
            async with semaphore:
                try:
                    texts = [n.text for n in chunk_nodes]
                    vecs = await self.embedding_service.embed_batch(texts)

                    if self.vector_store:
                        sparse_embs = await asyncio.to_thread(bm25_encoder.encode_batch_sparse_vectors, texts)
                        ids = await self.vector_store.store(
                            ctx.document_id,
                            chunk_nodes,
                            vecs,
                            sparse_embeddings=sparse_embs,
                        )
                        ctx.storage_ids.extend(ids)

                    pct = 40 + int(55 * (chunk_idx + 1) / n_chunks)
                    await report("embedding", pct, f"Indexing vectors: batch {chunk_idx + 1}/{n_chunks}...")
                except Exception as e:
                    logger.error("[%s] Vector indexing failed for batch %d: %s", ctx.document_id, chunk_idx, e)
                    ctx.errors.append(f"Batch {chunk_idx} failed: {str(e)}")

        tasks = []
        for idx, start in enumerate(range(0, len(ctx.nodes), chunk_size)):
            end = start + chunk_size
            tasks.append(_process(idx, ctx.nodes[start:end]))

        await asyncio.gather(*tasks)
        await bm25_encoder.save_async()
