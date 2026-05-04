"""
Ingestion Pipeline: Main orchestration for document parsing → hierarchy → embedding → storage.
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable
from dataclasses import dataclass

from app.adapters.base import IngestedNode, ParsingMetadata
from app.core.hardware import hardware
from app.adapters.parsers.manager import ParserManager
from app.utils.hierarchy_validator import HierarchyValidator, ValidationReport
from app.core.config import settings
from app.repositories.section_repository import SectionRepository

if TYPE_CHECKING:
    from app.adapters.base import BaseEmbedding, BaseVectorStore
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of ingestion pipeline."""

    success: bool
    document_id: str
    node_count: int
    nodes: list[IngestedNode]
    total_text_chars: int
    parse_metadata: ParsingMetadata
    validation_report: ValidationReport
    storage_ids: list[str]
    section_count: int = 0  # Number of sections stored in PostgreSQL
    errors: list[str] = None  # type: ignore[assignment]
    warnings: list[str] = None  # type: ignore[assignment]
    duration_ms: float = 0.0


# Type alias for clarity
ProgressCallback = Callable[[str, int, str], None]  # (stage, percent, message)


class IngestionService:
    """
    Main ingestion orchestration:
    1. Parse document (DoclingParser → ClassicParser fallback)
    2. Validate hierarchy
    3. Embed + store nodes in chunks (parallel embedding, incremental Qdrant writes)
    4. Report progress at each chunk via optional callback
    """

    def __init__(
        self,
        parser_manager: "ParserManager",
        embedding_service: BaseEmbedding | None = None,
        vector_store: BaseVectorStore | None = None,
        db_session: Session | None = None,
        section_repo: SectionRepository | None = None,
    ):
        self.parser_manager = parser_manager
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.db_session = db_session
        self.section_repo = section_repo
        self.validator = HierarchyValidator()

    def ingest(
        self,
        filename: str,
        content: bytes,
        user_id: str,
        document_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> "IngestionResult":
        """
        Synchronous ingestion pipeline with chunked embed+store and progress reporting.

        Progress stages (approximate %):
          5%  → starting parse
          30% → parse complete
          35% → hierarchy validation complete
          40-90% → chunked embed+store (incremental, 1 tick per chunk)
          100% → done

        Args:
            filename:          Original filename
            content:           Raw file bytes
            user_id:           User performing the upload
            document_id:       Unique document ID (UUID)
            progress_callback: Optional callable(stage, percent, message).
                               Called after each significant step and after each embed chunk.
        """
        start_time = time.time()
        errors: list[str] = []
        warnings: list[str] = []
        nodes: list[IngestedNode] = []
        parse_metadata: ParsingMetadata | None = None
        validation_report: ValidationReport | None = None
        storage_ids: list[str] = []

        def _cb(stage: str, percent: int, message: str = "") -> None:
            """Fire progress callback safely — never let a callback error crash the pipeline."""
            if progress_callback:
                try:
                    progress_callback(stage, percent, message)
                except Exception as cb_exc:
                    logger.warning("[%s] Progress callback error: %s", document_id, cb_exc)

        try:
            # ── Step 1: Parse ────────────────────────────────────────────────
            logger.info("[%s] Starting ingestion: %s", document_id, filename)
            _cb("parsing", 5, f"Parsing {filename}…")

            nodes, parse_metadata = self.parser_manager.parse(filename, content, document_id=document_id)
            logger.info("[%s] Parsed: %d nodes from %s", document_id, len(nodes), filename)
            _cb("parsing", 30, f"Parsed {len(nodes)} sections")

            # ── Step 2: Validate hierarchy ───────────────────────────────────
            _cb("parsing", 35, "Validating document structure…")
            validation_report = self.validator.validate(nodes)
            if not validation_report.is_valid:
                errors.extend(validation_report.errors)
                warnings.extend(validation_report.warnings)
                logger.warning(
                    "[%s] Validation: %d errors, %d warnings",
                    document_id,
                    len(errors),
                    len(warnings),
                )
            else:
                logger.info("[%s] Hierarchy valid (depth=%s)", document_id, validation_report.depth)

            # ── Step 2.5: Store Sections (if section data exists) ────────────
            section_count = 0
            sections_data = getattr(parse_metadata, "sections_data", None) or []
            if sections_data and self.db_session:
                _cb("parsing", 37, f"Storing {len(sections_data)} sections…")
                section_repo = self.section_repo or SectionRepository(self.db_session)
                section_ids = section_repo.store_sections(document_id, sections_data)
                section_count = len(section_ids)
                logger.info(
                    "[%s] Stored %d sections in PostgreSQL",
                    document_id,
                    section_count,
                )

            # ── Step 3: Embed + Store in chunks ──────────────────────────────
            if self.embedding_service and nodes:
                chunk_size = settings.ingestion_embedding_chunk_size
                n_chunks = math.ceil(len(nodes) / chunk_size) or 1
                store_parallelism = settings.ingestion_embed_parallelism or hardware.embed_parallelism
                store_parallelism = max(1, min(store_parallelism, 4))
                pending_store_tasks: deque[tuple[int, list[IngestedNode], Future[list[str]]]] = deque()

                # BM25 sparse encoder — always available, builds vocab on first use
                from app.utils.bm25_index import get_bm25_encoder

                bm25_encoder = get_bm25_encoder()
                bm25_ready = bm25_encoder.is_ready

                def _store_chunk(
                    chunk_document_id: str,
                    chunk_nodes: list[IngestedNode],
                    chunk_vecs: list[list[float]],
                ) -> list[str]:
                    if not self.vector_store:
                        return []
                    # Generate BM25 sparse vectors for hybrid search
                    sparse_embs = None
                    if bm25_ready:
                        sparse_embs = bm25_encoder.encode_batch_sparse_vectors([n.text for n in chunk_nodes])
                    return self.vector_store.store(
                        chunk_document_id,
                        chunk_nodes,
                        chunk_vecs,
                        sparse_embeddings=sparse_embs,
                    )

                with ThreadPoolExecutor(max_workers=store_parallelism) as store_executor:
                    for chunk_idx, chunk_start in enumerate(range(0, len(nodes), chunk_size)):
                        chunk_nodes = nodes[chunk_start : chunk_start + chunk_size]
                        chunk_texts = [n.text for n in chunk_nodes]

                        try:
                            # embed_batch handles internal parallelism via ThreadPoolExecutor
                            vecs = self.embedding_service.embed_batch(chunk_texts)

                            if self.vector_store:
                                pending_store_tasks.append(
                                    (
                                        chunk_idx,
                                        chunk_nodes,
                                        store_executor.submit(
                                            _store_chunk,
                                            document_id,
                                            chunk_nodes,
                                            vecs,
                                        ),
                                    )
                                )
                            else:
                                pct = 40 + int(50 * (chunk_idx + 1) / n_chunks)  # 40% → 90%
                                _cb(
                                    "embedding",
                                    pct,
                                    f"Indexing section {chunk_idx + 1}/{n_chunks}…",
                                )
                                logger.info(
                                    "[%s] Chunk %d/%d embedded (%d nodes) — storage disabled",
                                    document_id,
                                    chunk_idx + 1,
                                    n_chunks,
                                    len(chunk_nodes),
                                )

                            while len(pending_store_tasks) >= store_parallelism:
                                completed_idx, completed_nodes, completed_future = pending_store_tasks.popleft()
                                ids = completed_future.result()
                                storage_ids.extend(ids)
                                pct = 40 + int(50 * (completed_idx + 1) / n_chunks)  # 40% → 90%
                                _cb(
                                    "embedding",
                                    pct,
                                    f"Indexing section {completed_idx + 1}/{n_chunks}…",
                                )
                                logger.info(
                                    "[%s] Chunk %d/%d embedded+stored (%d nodes)",
                                    document_id,
                                    completed_idx + 1,
                                    n_chunks,
                                    len(completed_nodes),
                                )
                        except Exception as e:
                            logger.error(
                                "[%s] Chunk %d/%d embed failed: %s",
                                document_id,
                                chunk_idx + 1,
                                n_chunks,
                                e,
                            )
                            errors.append(f"Chunk {chunk_idx + 1} embed failed: {e}")
                            # Continue with remaining chunks — partial index beats total failure
                            continue

                    while pending_store_tasks:
                        completed_idx, completed_nodes, completed_future = pending_store_tasks.popleft()
                        try:
                            ids = completed_future.result()
                            storage_ids.extend(ids)
                            pct = 40 + int(50 * (completed_idx + 1) / n_chunks)  # 40% → 90%
                            _cb(
                                "embedding",
                                pct,
                                f"Indexing section {completed_idx + 1}/{n_chunks}…",
                            )
                            logger.info(
                                "[%s] Chunk %d/%d embedded+stored (%d nodes)",
                                document_id,
                                completed_idx + 1,
                                n_chunks,
                                len(completed_nodes),
                            )
                        except Exception as e:
                            logger.error(
                                "[%s] Chunk %d/%d store failed: %s",
                                document_id,
                                completed_idx + 1,
                                n_chunks,
                                e,
                            )
                            errors.append(f"Chunk {completed_idx + 1} store failed: {e}")
            else:
                if not self.embedding_service:
                    warnings.append("No embedding service configured — skipping vector indexing")
                elif not nodes:
                    warnings.append("No nodes produced — empty document?")

            duration_ms = (time.time() - start_time) * 1000

            # Determine success: fail if too many chunk errors (>50% of chunks)
            total_chunks = locals().get("n_chunks", len(nodes) if nodes else 0)
            error_threshold = max(1, int(total_chunks * 0.5)) if total_chunks > 0 else 1
            has_critical_failure = len(errors) > error_threshold

            if has_critical_failure:
                _cb("failed", 0, f"{len(errors)} chunk errors exceeded threshold")
                logger.warning(
                    "[%s] Ingestion partial failure: %d/%d chunks failed",
                    document_id,
                    len(errors),
                    n_chunks,
                )
            else:
                _cb("ready", 100, "Ingestion complete")

            result = IngestionResult(
                success=not has_critical_failure,
                document_id=document_id,
                node_count=len(nodes),
                nodes=nodes,
                total_text_chars=sum(len(n.text) for n in nodes),
                parse_metadata=parse_metadata,
                validation_report=validation_report,
                storage_ids=storage_ids,
                section_count=section_count,
                errors=errors,
                warnings=warnings,
                duration_ms=duration_ms,
            )

            logger.info(
                "[%s] ✓ Ingestion complete: %d nodes in %.0fms",
                document_id,
                result.node_count,
                duration_ms,
            )
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("[%s] ✗ Ingestion failed: %s", document_id, e)
            _cb("failed", 0, str(e))

            return IngestionResult(
                success=False,
                document_id=document_id,
                node_count=len(nodes),
                nodes=nodes,
                total_text_chars=sum(len(n.text) for n in nodes) if nodes else 0,
                parse_metadata=parse_metadata,
                validation_report=validation_report,
                storage_ids=[],
                errors=[str(e)] + errors,
                warnings=warnings,
                duration_ms=duration_ms,
            )
