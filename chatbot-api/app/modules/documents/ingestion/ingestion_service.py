"""
Ingestion Pipeline: Parse -> Validate -> Store Sections -> Embed & Index.
Uses LlamaParse/cloud markdown parsing + LlamaIndex for chunking + embedding + Qdrant indexing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from app.adapters.base import IngestedNode, ParsingMetadata
from app.adapters.parsers.docx_converter import convert_docx_to_pdf, is_docx
from app.adapters.parsers.llamaparse_adapter import LlamaParseParser
from app.modules.documents.ingestion.pipeline import run_ingestion_pipeline
from app.modules.documents.repositories import SectionRepository
from app.modules.documents.validators import HierarchyValidator, ValidationReport

if TYPE_CHECKING:
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
    tenant_id: str
    user_id: str
    nodes: list[IngestedNode] = field(default_factory=list)
    parse_metadata: ParsingMetadata | None = None
    validation_report: ValidationReport | None = None
    section_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)


ProgressCallback = Callable[[str, int, str], Any]


class IngestionService:
    """Ingestion orchestration using LlamaParse parser + LlamaIndex pipeline."""

    def __init__(
        self,
        redis_client: Any,
        db_session: AsyncSession | None = None,
        section_repo: SectionRepository | None = None,
    ):
        self.redis = redis_client
        self.parser = LlamaParseParser()
        self.db_session = db_session
        self.section_repo = section_repo
        self.validator = HierarchyValidator()

    async def ingest(
        self,
        filename: str,
        content: bytes,
        user_id: str,
        document_id: str,
        tenant_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestionResult:
        ctx = PipelineContext(filename, content, document_id, tenant_id, user_id)

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
            await self._store_sections_step(ctx, report)
            await self._vector_index_step(ctx, report)

            duration_ms = (time.time() - ctx.start_time) * 1000
            n_nodes = len(ctx.nodes)
            has_critical_failure = len(ctx.errors) > max(1, n_nodes * 0.5) if n_nodes > 0 else True

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
                storage_ids=[],
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
        """Parse document with LlamaParse/local markdown parser."""
        await report("parsing", 5, f"Parsing {ctx.filename}...")

        filename_to_parse = ctx.filename
        content_to_parse = ctx.content

        if is_docx(ctx.filename):
            await report("parsing", 7, "Converting DOCX to PDF for accurate OCR...")
            try:
                pdf_content, pdf_filename = await asyncio.to_thread(convert_docx_to_pdf, ctx.content, ctx.filename)
                content_to_parse = pdf_content
                filename_to_parse = pdf_filename
            except Exception as docx_err:
                logger.warning("DOCX->PDF conversion failed, falling back to direct parse: %s", docx_err)
                ctx.warnings.append(f"DOCX->PDF conversion failed: {docx_err} -- using direct DOCX parse")

        nodes, metadata = await self.parser.parse(filename_to_parse, content_to_parse, document_id=ctx.document_id)

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

        sections_data = getattr(metadata, "sections_data", None) or []
        metadata.sections_data = sections_data
        ctx.nodes = nodes
        ctx.parse_metadata = metadata

    async def _store_sections_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Store sections in DB."""
        sections_data = getattr(ctx.parse_metadata, "sections_data", None) or []
        if not sections_data or not self.db_session:
            return

        await report("parsing", 37, f"Saving {len(sections_data)} sections to database...")
        repo = self.section_repo or SectionRepository(self.db_session)
        section_ids = await repo.store_sections(ctx.document_id, ctx.tenant_id, sections_data)
        ctx.section_count = len(section_ids)

    async def _vector_index_step(self, ctx: PipelineContext, report: ProgressCallback) -> None:
        """Split, embed, and index documents via LlamaIndex pipeline."""
        if not ctx.nodes:
            logger.warning("[%s] No nodes to index", ctx.document_id)
            return

        await report("embedding", 40, "Đang bắt đầu embedding và ghi dữ liệu vào Qdrant...")

        sections_data = getattr(ctx.parse_metadata, "sections_data", None) or []
        embedding_start = 40
        embedding_end = 95
        section_total = len(sections_data)
        chunk_total = sum(int(section.get("chunk_count", 0) or 0) for section in sections_data)

        async def _on_pipeline_progress(phase: str, phase_processed: int, total_docs: int, total_stored: int) -> None:
            if total_docs <= 0:
                return
            ratio = total_stored / total_docs
            percent = embedding_start + int((embedding_end - embedding_start) * ratio)
            if phase == "section":
                message = f"Đang index section {phase_processed}/{section_total}, chuẩn bị chuyển sang chunk..."
            elif phase == "chunk":
                message = f"Đang index chunk {phase_processed}/{chunk_total}, dữ liệu đang được ghi vào Qdrant..."
            else:
                message = "Đang chuẩn bị dữ liệu index cho Qdrant..."
            await report(
                "embedding",
                min(embedding_end, max(embedding_start, percent)),
                message,
            )

        from app.modules.settings.runtime_manager import RuntimeProviderManager

        adapter = RuntimeProviderManager.get_instance().get_embedding_adapter()
        stored, updated_sections = await run_ingestion_pipeline(
            ctx.nodes,
            ctx.document_id,
            ctx.tenant_id,
            sections_data,
            progress_callback=_on_pipeline_progress,
            adapter=adapter,
        )
        if updated_sections and self.db_session:
            repo = self.section_repo or SectionRepository(self.db_session)
            await repo.store_sections(ctx.document_id, ctx.tenant_id, updated_sections)
            ctx.parse_metadata.sections_data = updated_sections
            ctx.section_count = len(updated_sections)

        await report("embedding", 95, "Embedding xong, đang hoàn tất ghi và xác nhận dữ liệu trong Qdrant...")
        logger.info("[%s] LlamaIndex pipeline stored %d nodes", ctx.document_id, stored)
