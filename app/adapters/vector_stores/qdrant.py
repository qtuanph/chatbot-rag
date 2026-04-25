"""
Qdrant Vector Store Adapter: Hybrid vector search with on-prem Qdrant.
Manages storage and retrieval of document embeddings.
"""

import logging
from typing import List, Optional, Dict, Any

from app.adapters.base import (
    BaseVectorStore,
    IngestedNode,
    RetrievedDocument,
)
from app.core.exceptions import (
    VectorStoreConnectionException,
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
        api_key: Optional[str] = None,
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
        self.client = None
        
        self._initialize_client()
        self._ensure_collection()

    def _initialize_client(self) -> None:
        """Initialize Qdrant client."""
        try:
            from qdrant_client import QdrantClient
            
            logger.info(f"Connecting to Qdrant at {self.url}...")
            
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
            
            # Test connection
            health = self.client.get_collections()
            logger.info(f"✓ Connected to Qdrant; {len(health.collections)} collections exist")
        
        except ImportError as e:
            raise VectorStoreConnectionException(
                "qdrant-client not installed",
                error_code="QDRANT_IMPORT_ERROR",
                details={'error': str(e)}
            )
        except Exception as e:
            raise VectorStoreConnectionException(
                f"Failed to connect to Qdrant at {self.url}: {str(e)}",
                error_code="QDRANT_CONNECTION_FAILED",
                details={'url': self.url, 'error': str(e)}
            )

    def _ensure_collection(self) -> None:
        """Ensure collection exists with named dense + sparse vectors.

        If collection exists but uses unnamed (legacy) vectors, it is deleted
        and recreated. This handles the migration from unnamed to named vectors.
        """
        try:
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
            )

            # Check if collection exists
            collections = self.client.get_collections()
            if any(col.name == self.collection_name for col in collections.collections):
                # Check if collection has named vectors (not legacy unnamed)
                info = self.client.get_collection(self.collection_name)
                vectors_config = info.config.params.vectors
                # Named vectors = dict, unnamed = single VectorParams
                if isinstance(vectors_config, dict) and "dense" in vectors_config:
                    logger.info("Collection '%s' exists with named vectors", self.collection_name)
                    return
                # Legacy collection with unnamed vectors — must recreate
                logger.warning(
                    "Collection '%s' uses legacy unnamed vectors — deleting and recreating with named vectors",
                    self.collection_name,
                )
                self.client.delete_collection(self.collection_name)

            # Create collection with named dense + sparse vectors for hybrid search

            # Create collection with named dense + sparse vectors for hybrid search
            logger.info(
                "Creating collection '%s' (dense + sparse-bm25, int8 quantized, HNSW m=16 ef_construct=128)...",
                self.collection_name,
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "sparse-bm25": SparseVectorParams(
                        index=SparseIndexParams(on_disk=False),
                        modifier=Modifier.IDF,
                    ),
                },
                quantization_config=ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    ),
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=128,
                ),
            )
            logger.info("Created collection '%s' with dense + sparse-bm25 vectors", self.collection_name)

        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to ensure collection '{self.collection_name}': {str(e)}",
                error_code="QDRANT_COLLECTION_CREATION_FAILED",
                details={'collection': self.collection_name, 'error': str(e)}
            )

    def health_check(self) -> bool:
        """Check if Qdrant is reachable and collection exists."""
        try:
            if not self.client:
                return False
            
            # Try to get collection info
            self.client.get_collection(self.collection_name)
            return True
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {str(e)}")
            return False

    def store(
        self,
        document_id: str,
        nodes: List[IngestedNode],
        embeddings: List[List[float]],
        sparse_embeddings: List | None = None,
    ) -> List[str]:
        """
        Store document nodes and embeddings in Qdrant with optional sparse vectors.

        Args:
            document_id: ID of document being stored
            nodes: List of IngestedNode objects
            embeddings: List of dense embedding vectors (must match nodes length)
            sparse_embeddings: Optional list of SparseVector for BM25 hybrid search

        Returns:
            List of stored node IDs
        """
        if len(nodes) != len(embeddings):
            raise VectorStoreOperationException(
                f"Node count ({len(nodes)}) != embedding count ({len(embeddings)})",
                error_code="QDRANT_MISMATCH"
            )

        try:
            from qdrant_client.models import PointStruct, SparseVector

            points = []
            stored_ids = []

            for idx, (node, embedding) in enumerate(zip(nodes, embeddings)):
                point_id = self._node_id_to_qdrant_id(node.node_id)

                # Build payload with rich metadata
                payload = {
                    'document_id': document_id,
                    'node_id': node.node_id,
                    'text': node.text,
                    'node_type': node.node_type.value if hasattr(node.node_type, 'value') else str(node.node_type),
                    'page_number': node.page_number,
                    'section_title': node.section_title,
                    'parent_id': node.parent_id,
                    'order': node.order,
                }

                # Add custom metadata
                if node.metadata:
                    payload['metadata'] = node.metadata

                # Named dense vector + optional sparse vector
                vector: dict = {"dense": embedding}
                if sparse_embeddings and idx < len(sparse_embeddings):
                    sparse_emb = sparse_embeddings[idx]
                    if sparse_emb is not None:
                        vector["sparse-bm25"] = sparse_emb

                point = PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
                points.append(point)
                stored_ids.append(node.node_id)

            # Upsert points
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            logger.info(
                "Stored %d nodes for document %s (sparse=%s)",
                len(points), document_id, "yes" if sparse_embeddings else "no",
            )
            return stored_ids

        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to store nodes in Qdrant: {str(e)}",
                error_code="QDRANT_STORE_FAILED",
                details={'document_id': document_id, 'node_count': len(nodes), 'error': str(e)}
            )

    def retrieve(
        self,
        query_vector: List[float],
        top_k: int = 5,
        document_id_filter: Optional[str] = None,
        document_ids_filter: Optional[List[str]] = None,
        section_ids_filter: Optional[List[str]] = None,
        sparse_vector=None,
    ) -> List[RetrievedDocument]:
        """
        Retrieve top-k documents using hybrid search (Dense + BM25 RRF fusion).

        When sparse_vector is provided, runs both dense (semantic) and sparse (BM25)
        prefetch queries in parallel and fuses with Reciprocal Rank Fusion (RRF).
        When sparse_vector is None, runs dense-only search.

        Args:
            query_vector: Dense query embedding vector
            top_k: Number of results to return
            document_id_filter: Optional filter to specific document
            document_ids_filter: Optional filter to multiple documents
            section_ids_filter: Optional filter to specific sections
            sparse_vector: Optional SparseVector from VietnameseBM25Encoder for hybrid search

        Returns:
            List of RetrievedDocument objects with scores

        Raises:
            VectorStoreOperationException: If retrieval fails
        """
        try:
            from qdrant_client.models import (
                Filter,
                FieldCondition,
                MatchValue,
                MatchAny,
                SearchParams,
                QuantizationSearchParams,
            )

            # Build filter conditions
            query_conditions = []
            if document_ids_filter:
                query_conditions.append(
                    FieldCondition(
                        key="document_id",
                        match=MatchAny(any=document_ids_filter),
                    )
                )
            elif document_id_filter:
                query_conditions.append(
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id_filter),
                    )
                )

            if section_ids_filter:
                query_conditions.append(
                    FieldCondition(
                        key="metadata.section_id",
                        match=MatchAny(any=section_ids_filter),
                    )
                )

            query_filter = Filter(must=query_conditions) if query_conditions else None

            if sparse_vector is not None:
                # ── Hybrid mode: Dense + BM25 with RRF fusion ─────────────
                from qdrant_client.models import Prefetch, FusionQuery, Fusion

                prefetch_list = [
                    # Sparse (BM25) prefetch
                    Prefetch(
                        query=sparse_vector,
                        using="sparse-bm25",
                        limit=min(top_k * 3, 60),
                        filter=query_filter,
                    ),
                    # Dense (semantic) prefetch with int8 rescoring
                    Prefetch(
                        query=query_vector,
                        using="dense",
                        limit=min(top_k * 3, 60),
                        filter=query_filter,
                        search_params=SearchParams(
                            hnsw_ef=128,
                            quantization=QuantizationSearchParams(
                                ignore=False,
                                rescore=True,
                                oversampling=2.0,
                            ),
                        ),
                    ),
                ]

                results = self.client.query_points(
                    collection_name=self.collection_name,
                    prefetch=prefetch_list,
                    query=FusionQuery(fusion=Fusion.RRF),
                    limit=top_k,
                    with_payload=True,
                    with_vectors=False,
                ).points

                logger.debug(
                    "Hybrid retrieved %d documents (dense+sparse RRF, top %d)",
                    len(results), top_k,
                )
            else:
                # ── Dense-only mode: single vector search ──────────────────
                results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    using="dense",
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                    with_vectors=False,
                    search_params=SearchParams(
                        hnsw_ef=128,
                        quantization=QuantizationSearchParams(
                            ignore=False,
                            rescore=True,
                            oversampling=2.0,
                        ),
                    ),
                ).points

                logger.debug(
                    "Dense-only retrieved %d documents (top %d)",
                    len(results), top_k,
                )

            # Convert to RetrievedDocument objects
            retrieved = []
            for point in results:
                payload = point.payload or {}
                retrieved_doc = RetrievedDocument(
                    node_id=payload.get('node_id', str(point.id)),
                    document_id=payload.get('document_id', 'unknown'),
                    text=payload.get('text', ''),
                    score=point.score,
                    metadata={
                        'page_number': payload.get('page_number'),
                        'section_title': payload.get('section_title'),
                        'parent_id': payload.get('parent_id'),
                        'node_type': payload.get('node_type'),
                        'custom': payload.get('metadata', {}),
                    },
                )
                retrieved.append(retrieved_doc)

            return retrieved

        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to retrieve from Qdrant: {str(e)}",
                error_code="QDRANT_RETRIEVE_FAILED",
                details={'top_k': top_k, 'hybrid': sparse_vector is not None, 'error': str(e)}
            )

    def delete(self, document_id: str) -> bool:
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
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter,
            )
            
            logger.info(f"Deleted all vectors for document {document_id} from Qdrant")
            return True
        
        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to delete document {document_id} from Qdrant: {str(e)}",
                error_code="QDRANT_DELETE_FAILED",
                details={'document_id': document_id, 'error': str(e)}
            )

    def delete_by_ids(self, point_ids: List[str | int]) -> bool:
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

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=normalized_ids),
            )
            return True
        except Exception as e:
            raise VectorStoreOperationException(
                f"Failed to delete points by id in Qdrant: {str(e)}",
                error_code="QDRANT_DELETE_BY_ID_FAILED",
                details={'point_ids': point_ids, 'error': str(e)}
            )
    def count(self, document_id: str) -> int:
        """
        Count vectors stored for a given document_id.

        Used for post-ingestion verification (expect > 0) and
        post-delete verification (expect == 0).
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            result = self.client.count(
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
            logger.warning(
                "Failed to count vectors for document %s: %s", document_id, e
            )
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
        qdrant_id = int.from_bytes(hash_bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF
        return qdrant_id

    def scroll(
        self,
        filter: Optional[Dict[str, Any]] = None,
        with_payload: bool = True,
        with_vector: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Scroll through all points that match the filter.

        Used by Tree API to fetch all nodes for a document.

        Args:
            filter: Qdrant filter dict (e.g., {"must": [{"key": "document_id", "match": {"value": "..."}}]})
            with_payload: Whether to include payload in results
            with_vector: Whether to include vector in results
            limit: Maximum number of points to return
            offset: Number of matching points to skip before collecting results

        Returns:
            List of point dicts with id, payload, and optionally vector
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Convert filter dict to Qdrant Filter object
            qdrant_filter = None
            if filter:
                # Build Qdrant Filter from dict
                must_conditions = []
                for condition in filter.get("must", []):
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
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qdrant_filter,
                limit=limit,
                offset=offset,
                with_payload=with_payload,
                with_vectors=with_vector,
            )

            # Convert results to list of dicts
            points = []
            for point in results[0]:  # scroll() returns (points, next_page_offset)
                point_dict = {
                    "id": str(point.id),
                    "payload": point.payload if with_payload else None,
                }
                if with_vector and point.vector is not None:
                    point_dict["vector"] = point.vector
                points.append(point_dict)

            return points

        except Exception as e:
            logger.error(f"Failed to scroll Qdrant: {str(e)}")
            raise VectorStoreOperationException(
                f"Failed to scroll Qdrant: {str(e)}",
                error_code="QDRANT_SCROLL_FAILED",
                details={'filter': filter, 'limit': limit, 'error': str(e)}
            )
