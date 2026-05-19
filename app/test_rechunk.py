import asyncio
from app.db.session import AsyncSessionLocal
from app.modules.documents.repositories import DocumentRepository, SectionRepository
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.config import settings
from app.core.redis import get_redis_client
from app.modules.documents.services import DocumentService
from app.modules.documents.utils.document_registry import DocumentRegistry


async def main():
    doc_id = "627463c9-41dc-4462-825f-74361cd797d0"
    redis = get_redis_client()
    vs = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size,
    )
    await vs.delete(doc_id)
    print("Deleted Qdrant")
    async with AsyncSessionLocal() as s:
        await SectionRepository(s).delete_sections(doc_id)
        await DocumentRepository(s).update_status(doc_id, status="ready", stage="ready", progress_percent=100)
        print("Reset to ready")
    async with AsyncSessionLocal() as s:
        svc = DocumentService(DocumentRepository(s), SectionRepository(s), DocumentRegistry(redis))
        result = await svc.rechunk_document(document_id=doc_id, user_id="admin")
        print("Queued:", result)
    await redis.aclose()


asyncio.run(main())
