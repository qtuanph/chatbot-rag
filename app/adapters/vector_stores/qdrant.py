"""
Qdrant Vector Store Adapter: Hybrid vector search with on-prem Qdrant.
Manages storage and retrieval of document embeddings.
"""

import logging
from typing import Any

from qdrant_client.models import (
    Distance,
    VectorParams,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    HnswConfigDiff,
    SparseVectorParams,
    SparseIndexParams,
    Modifier,
    PointStruct,
    Prefetch,
    FusionQuery,
    Fusion,
    RecommendQuery,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    PayloadSchemaType,
    OptimizersConfigDiff,
    SearchParams,
    QuantizationSearchParams,
)

from app.adapters.base import (
    BaseVectorStore,
    IngestedNode,
    RetrievedDocument,
)
from app.core.exceptions import (
    VectorStoreOperationException,
)

logger = logging.getLogger(__name__)


class QdrantVectorStore(BaseVectorStore):
    """
    Qdrant vector store backend for on-prem deployment.
    Supports hybrid search (dense vectors + BM25 sparse).
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection_name: str = "documents_vectors",
        vector_size: int = 1024,  # Vietnamese_Embedding_v2 dimension
        timeout: int = 30,
    ):
        """
        Initialize Qdrant vector store connection.

        Args:
            url: Qdrant server URL (e.g., http://qdrant:6333)
            api_key: Optional API key for Qdrant cloud
            collection_name: Name of Qdrant collection
            vector_size: Dimension of vectors (1024 for Vietnamese_Embedding_v2)
            timeout: Request timeout in seconds
        """
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.timeout = timeout
        self.client: Any = None
        self._initialized = False

    async def _get_client(self):
        """Lazy initialization of AsyncQdrantClient."""
        if self.client is None:
            from qdrant_client import AsyncQdrantClient

            self.client = AsyncQdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=self.timeout,
            )

        # One-time collection setup (using sync client for simplicity in setup)
        if not self._initialized:
            await self._ensure_collection_async()
            self._initialized = True

        return self.client

    async def _ensure_collection_async(self) -> None:
        """Ensure collection exists with dynamic hardware-optimized settings."""
        import asyncio

        try:
            from qdrant_client import QdrantClient

            from app.core.hardware import hardware

            def _setup():
                sync_client = QdrantClient(url=self.url, api_key=self.api_key, timeout=self.timeout)

                collections = sync_client.get_collections()
                if any(col.name == self.collection_name for col in collections.collections):
                    info = sync_client.get_collection(self.collection_name)
                    if isinstance(info.config.params.vectors, dict) and "dense" in info.config.params.vectors:
                        return
                    sync_client.delete_collection(self.collection_name)

                logger.info(
                    "Creating collection '%s' (m=%d, ef=%d, quant=%s)",
                    self.collection_name,
                    hardware.qdrant_hnsw_m,
                    hardware.qdrant_hnsw_ef,
                    hardware.qdrant_quantization,
                )

                sync_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "dense": VectorParams(size=self.vector_size, distance=Distance.COSINE),
                    },
                    sparse_vectors_config={
                        "sparse-bm25": SparseVectorParams(
                            index=SparseIndexParams(on_disk=False),
                            modifier=Modifier.IDF,
                        ),
                    },
                    quantization_config=(
                        ScalarQuantization(
                            scalar=ScalarQuantizationConfig(
                                type=ScalarType.INT8,
                                quantile=0.99,
                                always_ram=True,
                            ),
                        )
                        if hardware.qdrant_quantization
                        else None
                    ),
                    hnsw_config=HnswConfigDiff(
                        m=hardware.qdrant_hnsw_m,
                        ef_construct=hardware.qdrant_hnsw_ef,
                    ),
                    optimizers_config=OptimizersConfigDiff(
                        default_segment_number=max(hardware.qdrant_hnsw_m // 4, 1),
                    ),
                )

                sync_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                sync_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="metadata.section_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                sync_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="node_type",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                sync_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="metadata.section_title",
                    field_schema=PayloadSchemaType.TEXT,
                )

            await asyncio.to_thread(_setup)

        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection: {e}")
            raise VectorStoreOperationException(f"Qdrant setup failed: {e}")

    async def health_check(self) -> bool:
        """Check if Qdrant is reachable and collection exists."""
        try:
            client = await self._get_client()
            await client.get_collection(self.collection_name)
            return True
        except Exception:
            return False

    async def store(
        self,
        document_id: str,
        nodes: list[IngestedNode],
        embeddings: list[list[float]],
        sparse_embeddings: list[Any] | None = None,
    ) -> list[str]:
        """
        Store multiple nodes and their embeddings in Qdrant.
        Includes full section context in payload to avoid DB lookups during RAG.
        """
        try:
            client = await self._get_client()
            points = []
            for i, node in enumerate(nodes):
                # Ensure we have a valid point ID
                point_id = self._node_id_to_qdrant_id(node.node_id)

                # Build rich payload for "DB-less" RAG retrieval
                payload = {
                    "node_id": node.node_id,
                    "document_id": document_id,
                    "document_title": node.metadata.get("document_title", ""),
                    "text": node.text,
                    "page_number": node.page_number,
                    "section_title": node.section_title,
                    "parent_id": node.parent_id,
                    "node_type": node.node_type,
                    "metadata": node.metadata or {},
                    # Enhanced RAG fields: Store the full section context here
                    "section_content": node.metadata.get("section_content", ""),
                    "breadcrumb": node.metadata.get("breadcrumb", []),
                }

                vectors = {"dense": embeddings[i]}
                if sparse_embeddings and sparse_embeddings[i]:
                    vectors["sparse-bm25"] = sparse_embeddings[i]

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vectors,
                        payload=payload,
                    )
                )

            # Batch upsert
            await client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )

            return [str(p.id) for p in points]

        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to store nodes in Qdrant: {str(e)}",
                error_code="QDRANT_STORE_FAILED",
                details={"document_id": document_id, "node_count": len(nodes), "error": str(e)},
            )

    async def retrieve(
        self,
        query_vectors: list[list[float]],
        top_k: int = 5,
        document_ids_filter: list[str] | None = None,
        sparse_vectors: list[Any] | None = None,
        positive_point_ids: list[str] | None = None,
        negative_point_ids: list[str] | None = None,
    ) -> list[RetrievedDocument]:
        """
        Retrieve top-k documents using Unified Multi-Intent Search.
        Supports Multi-Query expansion (multiple query_vectors) and Hybrid (Sparse) search
        with native Server-Side Fusion (RRF).
        """
        try:
            # Build global filter
            query_conditions = []
            if document_ids_filter:
                query_conditions.append(FieldCondition(key="document_id", match=MatchAny(any=document_ids_filter)))
            query_filter = Filter(must=query_conditions) if query_conditions else None

            # ── Unified Prefetch List ────────────────────────────────────────
            prefetch_list = []

            # Handle multiple query vectors (Multi-Query Expansion)
            for i, d_vec in enumerate(query_vectors):
                # 1. Dense Search per query
                prefetch_list.append(
                    Prefetch(
                        query=d_vec,
                        using="dense",
                        limit=top_k * 2,
                        filter=query_filter,
                    )
                )

                # 2. Sparse Search per query (if available)
                if sparse_vectors and i < len(sparse_vectors) and sparse_vectors[i]:
                    prefetch_list.append(
                        Prefetch(
                            query=sparse_vectors[i],
                            using="sparse-bm25",
                            limit=top_k * 2,
                            filter=query_filter,
                        )
                    )

            # 3. Recommendation Signals (if any)
            pos_ids = [self._node_id_to_qdrant_id(pid) for pid in (positive_point_ids or [])]
            neg_ids = [self._node_id_to_qdrant_id(nid) for nid in (negative_point_ids or [])]
            if pos_ids or neg_ids:
                prefetch_list.append(
                    Prefetch(
                        query=RecommendQuery(positive=pos_ids, negative=neg_ids, strategy="best_score"),
                        using="dense",
                        limit=top_k * 2,
                        filter=query_filter,
                    )
                )

            # 4. Execute Unified Query with RRF Fusion and Native Grouping
            client = await self._get_client()
            from app.core.hardware import hardware

            # Qdrant 1.17+ Grouping + Fusion is extremely powerful for RAG
            response = await client.query_points_groups(
                collection_name=self.collection_name,
                prefetch=prefetch_list,
                query=FusionQuery(fusion=Fusion.RRF),
                group_by="metadata.section_id",
                group_capacity=3,  # Max 3 chunks per section to ensure diversity
                limit=top_k,  # Return top_k unique sections
                with_payload=True,
                search_params=SearchParams(
                    hnsw_ef=hardware.qdrant_hnsw_ef,
                    quantization=(
                        QuantizationSearchParams(
                            ignore=False,
                            rescore=True,  # Rescore to maintain accuracy after INT8 compression
                        )
                        if hardware.qdrant_quantization
                        else None
                    ),
                ),
            )

            # Flatten groups into a single list for the RAG pipeline
            results = []
            for group in response.groups:
                # Add the best hit from each group to results
                if group.hits:
                    results.extend(group.hits)

            # Map to domain models
            return [
                RetrievedDocument(
                    node_id=str(p.payload.get("node_id", p.id)),
                    document_id=str(p.payload.get("document_id", "unknown")),
                    text=str(p.payload.get("text", "")),
                    score=p.score,
                    metadata={
                        "page_number": p.payload.get("page_number"),
                        "section_title": p.payload.get("section_title"),
                        "section_content": p.payload.get("section_content", ""),
                        "breadcrumb": p.payload.get("breadcrumb", []),
                        "custom": p.payload.get("metadata", {}),
                    },
                )
                for p in results
            ]

        except Exception as e:
            raise VectorStoreOperationException(
                f"Hybrid multi-query retrieval failed: {e}", error_code="QDRANT_QUERY_FAILED"
            )

    async def retrieve_grouped(
        self,
        query_vectors: list[list[float]],
        group_by: str = "metadata.section_id",
        group_size: int = 3,
        top_groups: int = 5,
        document_ids_filter: list[str] | None = None,
    ) -> list[RetrievedDocument]:
        """
        Retrieve top groups (e.g., sections) using Qdrant's native grouping.
        Useful for retrieving full sections with their best chunks.
        """
        try:
            client = await self._get_client()
            # Note: Grouping with Fusion (RRF) is currently complex in Qdrant API.
            # We use the primary query vector for grouping.
            query_vector = query_vectors[0]

            # Build filter
            query_conditions = []
            if document_ids_filter:
                query_conditions.append(FieldCondition(key="document_id", match=MatchAny(any=document_ids_filter)))
            query_filter = Filter(must=query_conditions) if query_conditions else None

            # Search with grouping
            response = await client.search_groups(
                collection_name=self.collection_name,
                query=query_vector,
                group_by=group_by,
                group_size=group_size,
                limit=top_groups,
                query_filter=query_filter,
                with_payload=True,
            )
            results = response.groups

            retrieved = []
            for group in results:
                for point in group.hits:
                    retrieved.append(
                        RetrievedDocument(
                            node_id=str(point.payload.get("node_id", point.id)),
                            document_id=str(point.payload.get("document_id", "unknown")),
                            text=str(point.payload.get("text", "")),
                            score=point.score,
                            metadata={
                                "page_number": point.payload.get("page_number"),
                                "section_title": point.payload.get("section_title"),
                                "section_content": point.payload.get("section_content", ""),
                                "breadcrumb": point.payload.get("breadcrumb", []),
                                "custom": point.payload.get("metadata", {}),
                            },
                        )
                    )
            return retrieved

        except Exception as e:
            raise VectorStoreOperationException(f"Grouped retrieval failed: {e}", error_code="QDRANT_GROUP_FAILED")

    async def delete(self, document_id: str) -> bool:
        """
        Delete all vectors for a document.

        Args:
            document_id: ID of document to delete

        Returns:
            True if deletion succeeded

        Raises:
            VectorStoreOperationException: If deletion fails
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Delete all points with matching document_id
            delete_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            )

            client = await self._get_client()
            await client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter,
            )

            logger.info(f"Deleted all vectors for document {document_id} from Qdrant")
            return True

        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to delete document {document_id} from Qdrant: {str(e)}",
                error_code="QDRANT_DELETE_FAILED",
                details={"document_id": document_id, "error": str(e)},
            )

    async def delete_by_ids(self, point_ids: list[str | int]) -> bool:
        """Delete specific Qdrant points by point IDs."""
        try:
            from qdrant_client.models import PointIdsList

            normalized_ids: list[int | str] = []
            for point_id in point_ids:
                if point_id is None:
                    continue
                try:
                    normalized_ids.append(int(str(point_id)))
                except (TypeError, ValueError):
                    normalized_ids.append(str(point_id))

            if not normalized_ids:
                return True

            client = await self._get_client()
            await client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=normalized_ids),
            )
            return True
        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to delete points by id in Qdrant: {str(e)}",
                error_code="QDRANT_DELETE_BY_ID_FAILED",
                details={"point_ids": point_ids, "error": str(e)},
            )

    async def count(self, document_id: str) -> int:
        """
        Count vectors stored for a given document_id (Async).
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            client = await self._get_client()

            result = await client.count(
                collection_name=self.collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                ),
                exact=True,
            )
            return result.count
        except Exception as e:
            logger.warning("Failed to count vectors for document %s: %s", document_id, e)
            return -1  # -1 signals error, not zero

    def _node_id_to_qdrant_id(self, node_id: str) -> int:
        """
        Convert node UUID to Qdrant integer ID.
        Qdrant requires integer point IDs.
        """
        # Hash UUID to stable integer
        import hashlib

        hash_bytes = hashlib.sha256(node_id.encode()).digest()
        # Take first 8 bytes and convert to int (max 2^63-1 for Qdrant)
        qdrant_id = int.from_bytes(hash_bytes[:8], byteorder="big") & 0x7FFFFFFFFFFFFFFF
        return qdrant_id

    async def scroll(
        self,
        query_filter: dict[str, Any | None] = None,
        with_payload: bool = True,
        with_vector: bool = False,
        limit: int = 100,
        offset: Any | None = None,
    ) -> tuple[list[dict[str, Any]], Any | None]:
        """
        Scroll through all points that match the filter (Async).
        Returns a tuple of (points, next_page_offset).
        """
        try:
            client = await self._get_client()

            # Convert filter dict to Qdrant Filter object
            qdrant_filter = None
            if query_filter:
                # Build Qdrant Filter from dict
                must_conditions = []
                for condition in query_filter.get("must", []):
                    key = condition.get("key")
                    match = condition.get("match", {})

                    if "value" in match:
                        must_conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=match["value"]),
                            )
                        )

                if must_conditions:
                    qdrant_filter = Filter(must=must_conditions)

            # Scroll through points
            results = await client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qdrant_filter,
                limit=limit,
                offset=offset,
                with_payload=with_payload,
                with_vectors=with_vector,
            )

            # Convert results to list of dicts
            points = []
            points_list, next_page_offset = results
            for point in points_list:
                point_dict = {
                    "id": str(point.id),
                    "payload": point.payload if with_payload else None,
                }
                if with_vector and point.vector is not None:
                    point_dict["vector"] = point.vector
                points.append(point_dict)

            return points, next_page_offset

        except Exception as e:
            logger.error(f"Failed to scroll Qdrant: {str(e)}")
            raise VectorStoreOperationException(
                f"Failed to scroll Qdrant: {str(e)}",
                error_code="QDRANT_SCROLL_FAILED",
                details={"filter": query_filter, "limit": limit, "error": str(e)},
            )
