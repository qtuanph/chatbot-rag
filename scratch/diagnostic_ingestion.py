
import asyncio
import sys
import os

# Ensure we can import app
sys.path.append(os.getcwd())

from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def diagnostic(doc_id):
    print(f"--- Diagnostic for Document: {doc_id} ---")
    
    # 1. Check PostgreSQL Sections
    async with AsyncSessionLocal() as session:
        # Check sections
        res = await session.execute(text("SELECT count(*) FROM document_sections WHERE document_id = :id"), {"id": doc_id})
        pg_count = res.scalar()
        print(f"Postgres Sections Count: {pg_count}")
        
        # Check document record and its metadata
        res = await session.execute(text("SELECT status, metadata FROM documents WHERE id = :id"), {"id": doc_id})
        doc_info = res.fetchone()
        if doc_info:
            status = doc_info[0]
            meta = doc_info[1] or {}
            node_count = meta.get("stats", {}).get("node_count", 0)
            print(f"DB Record: status={status}, node_count (from meta)={node_count}")
        else:
            print("DB Record: NOT FOUND")

    # 2. Check Qdrant Vectors
    vs = QdrantVectorStore(
        url=settings.qdrant_url,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size
    )
    # The count method in QdrantVectorStore might need document_id
    try:
        q_count = await vs.count(doc_id)
        print(f"Qdrant Vectors Count: {q_count}")
    except Exception as e:
        print(f"Qdrant count failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnostic_ingestion.py <document_id>")
        sys.exit(1)
    
    target_id = sys.argv[1]
    asyncio.run(diagnostic(target_id))
