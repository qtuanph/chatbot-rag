
import asyncio
import sys
import os

# Add /app to sys.path
sys.path.append("/app")

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.modules.documents.cleanup_service import CleanupService
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.section_repository import SectionRepository
from app.utils.document_registry import DocumentRegistry

async def hard_delete(doc_id: str):
    print(f"Starting hard delete for document: {doc_id}")
    
    # Initialize redis client
    redis_client = get_redis_client()
    
    async with AsyncSessionLocal() as session:
        doc_repo = DocumentRepository(session)
        sec_repo = SectionRepository(session)
        registry = DocumentRegistry(client=redis_client)
        cleanup_service = CleanupService(doc_repo, sec_repo, registry)
        
        try:
            await cleanup_service.hard_delete_document(doc_id)
            print(f"Successfully hard deleted document {doc_id}")
        except Exception as e:
            print(f"Error during hard delete: {e}")
            # Fallback: force delete from DB if service fails
            try:
                from sqlalchemy import text
                await session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})
                await session.commit()
                print(f"Forced DB delete for {doc_id}")
            except Exception as e2:
                print(f"Total failure: {e2}")
    
    # Close redis
    await redis_client.aclose()

if __name__ == "__main__":
    doc_id = "0fd42385-3f37-4593-bfc1-9cf83ebfbec7"
    asyncio.run(hard_delete(doc_id))
