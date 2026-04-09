"""
Ingestion Pipeline: Main orchestration for document parsing → hierarchy → embedding → storage.
"""

import logging
from typing import List
from dataclasses import dataclass
import time

from app.adapters.base import IngestedNode, ParsingMetadata
from app.services.ingestion.parser_manager import ParserManager
from app.services.ingestion.hierarchy_validator import HierarchyValidator, ValidationReport
logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of ingestion pipeline."""
    success: bool
    document_id: str
    node_count: int
    nodes: List[IngestedNode]
    total_text_chars: int
    parse_metadata: ParsingMetadata
    validation_report: ValidationReport
    storage_ids: List[str]
    errors: List[str]
    warnings: List[str]
    duration_ms: float


class IngestionPipeline:
    """
    Main ingestion orchestration:
    1. Parse document (DoclingParser → ClassicParser fallback)
    2. Validate hierarchy
    3. Embed nodes (BGE-M3)
    4. Store in PostgreSQL + Qdrant + MinIO
    """

    def __init__(
        self,
        parser_manager: 'ParserManager',
        embedding_service: 'BaseEmbedding' = None,
        vector_store: 'BaseVectorStore' = None,
    ):
        self.parser_manager = parser_manager
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.validator = HierarchyValidator()

    async def ingest_async(
        self,
        filename: str,
        content: bytes,
        user_id: str,
        document_id: str,
    ) -> IngestionResult:
        """
        Async ingestion pipeline (main entry point).
        
        Args:
            filename: Original filename
            content: Raw file bytes
            user_id: User performing upload
            document_id: Unique document ID (UUID)
        
        Returns:
            IngestionResult with detailed status
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.ingest, filename, content, user_id, document_id)

    def ingest(
        self,
        filename: str,
        content: bytes,
        user_id: str,
        document_id: str,
    ) -> IngestionResult:
        """
        Synchronous ingestion pipeline.
        """
        start_time = time.time()
        errors = []
        warnings = []
        nodes: List[IngestedNode] = []
        parse_metadata: ParsingMetadata = None
        validation_report: ValidationReport = None
        storage_ids: List[str] = []
        
        try:
            # Step 1: Parse document
            logger.info(f"[{document_id}] Starting ingestion: {filename}")
            nodes, parse_metadata = self.parser_manager.parse(filename, content)
            logger.info(f"[{document_id}] Parsed: {len(nodes)} nodes from {filename}")
            
            # Step 2: Validate hierarchy
            validation_report = self.validator.validate(nodes)
            if not validation_report.is_valid:
                errors.extend(validation_report.errors)
                warnings.extend(validation_report.warnings)
                logger.warning(f"[{document_id}] Validation issues: {len(errors)} errors, {len(warnings)} warnings")
            else:
                logger.info(f"[{document_id}] Hierarchy valid: depth={validation_report.depth}")
            
            # Step 3: Embed nodes (if embedding service available)
            embeddings = []
            if self.embedding_service:
                try:
                    logger.info(f"[{document_id}] Embedding {len(nodes)} nodes...")
                    texts = [node.text for node in nodes]
                    embeddings = self.embedding_service.embed_batch(texts)
                    logger.info(f"[{document_id}] Embedded: {len(embeddings)} vectors")
                except Exception as e:
                    logger.warning(f"[{document_id}] Embedding failed: {str(e)}")
                    warnings.append(f"Embedding failed: {str(e)}")
            
            # Step 4: Store in vector store (if available)
            if self.vector_store and embeddings:
                try:
                    storage_ids = self.vector_store.store(document_id, nodes, embeddings)
                    logger.info(f"[{document_id}] Stored in Qdrant: {len(storage_ids)} nodes")
                except Exception as e:
                    logger.error(f"[{document_id}] Vector store failed: {str(e)}")
                    errors.append(f"Vector store store failed: {str(e)}")
            
            duration_ms = (time.time() - start_time) * 1000
            
            result = IngestionResult(
                success=True,
                document_id=document_id,
                node_count=len(nodes),
                nodes=nodes,
                total_text_chars=sum(len(n.text) for n in nodes),
                parse_metadata=parse_metadata,
                validation_report=validation_report,
                storage_ids=storage_ids,
                errors=errors,
                warnings=warnings,
                duration_ms=duration_ms,
            )
            
            logger.info(f"[{document_id}] ✓ Ingestion complete: {result.node_count} nodes in {duration_ms:.0f}ms")
            return result
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[{document_id}] ✗ Ingestion failed: {str(e)}")

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
