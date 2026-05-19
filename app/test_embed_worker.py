"""Test 4 concurrent embedding calls to ai-engine."""

import asyncio, httpx, time


async def send_one(idx):
    texts = [f"test sentence {i} for batch {idx}" for i in range(32)]
    async with httpx.AsyncClient(timeout=600) as cl:
        t0 = time.time()
        r = await cl.post(
            "http://ai-engine:8000/embed",
            json={"texts": texts, "batch_size": 32, "normalize": True, "task_type": "passage"},
        )
        t1 = time.time()
        print(f"Batch {idx}: status={r.status_code}, time={t1-t0:.1f}s")


async def main():
    t_start = time.time()
    await asyncio.gather(*[send_one(i) for i in range(4)])
    print(f"Total: {time.time()-t_start:.1f}s")


asyncio.run(main())
