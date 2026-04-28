"""
Services module: reorganized into logical subpackages.

Backward-compatibility re-exports for existing imports.
New code should import from subpackages directly:
  - app.services.auth.*
  - app.services.documents.*
  - app.services.retrieval.*
  - app.services.chat.*
  - app.services.system.*
  - app.services.ingestion.*
"""

# Auth services
from app.services.auth.service import create_access_token, hash_password, verify_password
from app.services.auth.token_blacklist import TokenBlacklist
from app.services.auth.throttle import RequestThrottle

# Document services
from app.services.documents.registry import DocumentRecord, DocumentRegistry
from app.services.documents.cleanup import hard_delete_document

# Retrieval services
from app.services.retrieval.rag import (
    retrieve_context,
    build_answer,
    RagContext,
    RagNode,
    RagSection,
    invalidate_doc_ids_cache,
)
from app.services.retrieval.cache import QueryEmbeddingCache
from app.services.retrieval.bm25_index import get_bm25_encoder, build_bm25_index_from_qdrant, update_bm25_index
from app.services.retrieval.reranker import get_reranker, VietnameseReranker
from app.services.retrieval.query_expand import expand_query

# Chat services
from app.services.chat.store import ChatStore
from app.services.chat.memory import UserMemoryService

# System services
from app.services.system.health import build_health_payload
from app.services.system.audit import record_audit, safe_record_audit

# Ingestion services
from app.services.ingestion.pipeline import IngestionPipeline, IngestionResult
from app.services.ingestion.parser_manager import ParserManager
from app.services.ingestion.hierarchy_validator import HierarchyValidator, ValidationReport
from app.services.ingestion.recovery import PipelineRecoveryManager
from app.services.ingestion.rule_based_refiner import RuleBasedRefiner

__all__ = [
    # Auth
    "create_access_token",
    "hash_password",
    "verify_password",
    "TokenBlacklist",
    "RequestThrottle",
    # Documents
    "DocumentRecord",
    "DocumentRegistry",
    "hard_delete_document",
    # Retrieval
    "retrieve_context",
    "build_answer",
    "RagContext",
    "RagNode",
    "RagSection",
    "invalidate_doc_ids_cache",
    "QueryEmbeddingCache",
    "get_bm25_encoder",
    "build_bm25_index_from_qdrant",
    "update_bm25_index",
    "get_reranker",
    "VietnameseReranker",
    "expand_query",
    # Chat
    "ChatStore",
    "UserMemoryService",
    # System
    "build_health_payload",
    "record_audit",
    "safe_record_audit",
    # Ingestion
    "IngestionPipeline",
    "IngestionResult",
    "ParserManager",
    "HierarchyValidator",
    "ValidationReport",
    "PipelineRecoveryManager",
    "RuleBasedRefiner",
]
