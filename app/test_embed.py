import time, asyncio, httpx


async def test():
    start = time.time()
    async with httpx.AsyncClient(timeout=600) as cl:
        r = await cl.post(
            "http://localhost:8000/embed",
            json={
                "texts": [
                    "test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence test sentence "
                ]
                * 32,
                "batch_size": 32,
                "normalize": True,
                "task_type": "passage",
            },
        )
    elapsed = time.time() - start
    result = r.json()
    emb_count = len(result.get("embeddings", []))
    emb_dim = len(result["embeddings"][0]) if emb_count else 0
    print(f"Status: {r.status_code}, Time: {elapsed:.1f}s")
    print(f"Embeddings: {emb_count} x {emb_dim}")


asyncio.run(test())
