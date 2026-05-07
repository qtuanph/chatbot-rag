
import pytest
import asyncio
import io
from httpx import AsyncClient
from app.utils.auth import create_access_token
from app.core.config import settings

@pytest.mark.asyncio
async def test_document_upload_and_delete(client: AsyncClient):
    # 1. Generate auth token for admin
    user_id = "019e00af-df32-7e67-aca0-53b704112ac0"
    token = create_access_token(subject=user_id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload document
    test_file_content = b"This is a test document content for RAG pipeline validation."
    files = {"file": ("test_doc.txt", test_file_content, "text/plain")}
    
    response = await client.post(
        f"{settings.api_v1_prefix}/documents/upload",
        files=files,
        headers=headers
    )
    
    assert response.status_code == 201
    data = response.json()
    doc_id = data["id"]
    assert doc_id is not None
    print(f"\n[Test] Uploaded document ID: {doc_id}")

    # 3. Poll for status (wait for 'completed')
    max_retries = 30
    status = "processing"
    for i in range(max_retries):
        status_resp = await client.get(
            f"{settings.api_v1_prefix}/documents/{doc_id}",
            headers=headers
        )
        assert status_resp.status_code == 200
        status = status_resp.json()["status"]
        print(f"[Test] Current status: {status}")
        
        if status == "completed":
            break
        if status == "failed":
            pytest.fail("Document ingestion failed")
            
        await asyncio.sleep(2)
    
    assert status == "completed", "Document ingestion timed out"

    # 4. Search for content (Verify vectors are indexed)
    search_resp = await client.get(
        f"{settings.api_v1_prefix}/chat/search?q=test document content",
        headers=headers
    )
    assert search_resp.status_code == 200
    search_results = search_resp.json()
    assert len(search_results) > 0
    print(f"[Test] Content found in retrieval: {len(search_results)} results")

    # 5. Delete document
    del_resp = await client.delete(
        f"{settings.api_v1_prefix}/documents/{doc_id}",
        headers=headers
    )
    assert del_resp.status_code == 200
    print(f"[Test] Delete request sent for document {doc_id}")

    # 6. Verify it's gone
    for i in range(10):
        check_resp = await client.get(
            f"{settings.api_v1_prefix}/documents/{doc_id}",
            headers=headers
        )
        if check_resp.status_code == 404:
            print("[Test] Document confirmed deleted (404)")
            break
        await asyncio.sleep(1)
    else:
        pytest.fail("Document was not deleted in time")
