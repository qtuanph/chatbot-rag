"""
Ingestion Pipeline: Parse → Validate → Store Sections → Embed & Index.
Uses Docling for OCR parsing and LlamaIndex IngestionPipeline for split + embed.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import TYPE_CHECKING, Callable, Any
from dataclasses import dataclass, field

from llama_index.core.schema import Document as LlamaDocument

from app.adapters.base import IngestedNode, ParsingMetadata
from app.adapters.parsers.llamaparse_adapter import LlamaParseParser
from app.adapters.parsers.docx_converter import is_docx, convert_docx_to_pdf
from app.modules.documents.validators import HierarchyValidator, ValidationReport
from app.modules.documents.ingestion.llama_pipeline import LlamaIngestionPipeline
from app.core.config import settings
from app.modules.documents.repositories import SectionRepository
from app.core.hardware import hardware

if TYPE_CHECKING:
    from app.adapters.base import BaseEmbedding, BaseVectorStore
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
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
    """Ingestion orchestration using DoclingParser + LlamaIndex IngestionPipeline."""

    def __init__(
        self,
        redis_client: Any,
        embedding_service: BaseEmbedding | None = None,
        vector_store: BaseVectorStore | None = None,
        db_session: AsyncSession | None = None,
        section_repo: SectionRepository | None = None,
    ):
        self.redis = redis_client
        self.parser = LlamaParseParser()
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.db_session = db_session
        self.section_repo = section_repo
        self.validator = HierarchyValidator()
        self.llama_pipeline = LlamaIngestionPipeline()

    async def ingest(
        self,
        filename: str,
        content: bytes,
        user_id: str,
        document_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestionResult:
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
            await self._parse_step(ctx, report)
            await self._validate_step(ctx, report)
            await self._store_sections_step(ctx, report)
            await self._vector_index_step(ctx, report)

            duration_ms = (time.time() - ctx.start_time) * 1000
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

    async def _parse_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Parse document with Docling + EasyOCR."""
        await report("parsing", 5, f"Parsing {ctx.filename} using Docling...")

        filename_to_parse = ctx.filename
        content_to_parse = ctx.content

        if is_docx(ctx.filename):
            await report("parsing", 7, "Converting DOCX to PDF for accurate OCR...")
            try:
                pdf_content, pdf_filename = convert_docx_to_pdf(ctx.content, ctx.filename)
                content_to_parse = pdf_content
                filename_to_parse = pdf_filename
            except Exception as docx_err:
                logger.warning("DOCX→PDF conversion failed, falling back to direct parse: %s", docx_err)
                ctx.warnings.append(f"DOCX→PDF conversion failed: {docx_err} — using direct DOCX parse")

        nodes, metadata = await self.parser.parse(filename_to_parse, content_to_parse, document_id=ctx.document_id)

        # Save raw markdown to S3 for future re-chunking / agentic RAG
        if getattr(metadata, "raw_md_content", None):
            try:
                from app.adapters.storage import build_storage

                storage = build_storage()
                md_bytes = metadata.raw_md_content.encode("utf-8")
                await asyncio.to_thread(storage.save_bytes, ctx.document_id, "ocr_output.md", md_bytes)
                logger.info("[%s] Saved OCR markdown to S3", ctx.document_id)
            except Exception as md_err:
                logger.warning("[%s] Failed to save OCR markdown to S3: %s", ctx.document_id, md_err)
                ctx.warnings.append(f"Failed to persist OCR markdown: {md_err}")

        # Convert IngestedNodes to LlamaIndex Documents for IngestionPipeline
        llama_docs = []
        for n in nodes:
            llama_docs.append(
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

        # Run LlamaIndex IngestionPipeline (SentenceSplitter + Embed)
        llama_nodes = await self.llama_pipeline.arun(llama_docs)

        # Convert back to IngestedNode format for downstream compatibility
        ctx.nodes = self.llama_pipeline.convert_ingested_nodes(llama_nodes, ctx.document_id, metadata.source_format)
        logger.info("[%s] LlamaIndex pipeline produced %d nodes", ctx.document_id, len(ctx.nodes))

        sections_data = getattr(metadata, "sections_data", None) or []
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

        section_map = {s["section_id"]: s for s in sections_data}
        for node in ctx.nodes:
            sec_id = node.metadata.get("section_id")
            if sec_id and sec_id in section_map:
                sec = section_map[sec_id]
                node.metadata["section_content"] = sec.get("content", "")
                node.metadata["breadcrumb"] = sec.get("breadcrumb", [])
                node.metadata["level"] = sec.get("level", 0)

    async def _vector_index_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Embedding and Vector storage indexing (BM25 + Qdrant)."""
        if not self.embedding_service or not ctx.nodes:
            logger.warning(
                "[%s] _vector_index_step SKIPPED: embedding=%s, nodes=%d",
                ctx.document_id,
                bool(self.embedding_service),
                len(ctx.nodes),
            )
            return

        chunk_size = settings.ingestion_embedding_chunk_size
        n_chunks = math.ceil(len(ctx.nodes) / chunk_size) or 1

        from app.modules.documents.utils import get_async_bm25_encoder

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
