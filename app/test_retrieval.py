import asyncio
from app.modules.chat.retrieval.retrieval_service import RetrievalService
from app.core.redis import get_redis_client
from app.db.session import AsyncSessionLocal


async def test():
    redis = get_redis_client()
    svc = RetrievalService(redis)
    async with AsyncSessionLocal() as session:
        ctx = await svc.retrieve_context(session=session, query="Nhiem vu cua nguoi dung la gi?", limit=5)
    print(f"Nodes: {len(ctx.nodes)}, Sections: {len(ctx.sections) if ctx.sections else 0}")
    for i, n in enumerate(ctx.nodes[:3]):
        sid = n.section_id or "N/A"
        print(f"[{i}] section={sid} heading={n.heading[:40] if n.heading else 'N/A'} score={n.score:.3f}")
        print(f"    text: {(n.full_text or '')[:80]}...")
    if ctx.sections:
        print(f"\nTop sections:")
        for i, s in enumerate(ctx.sections[:3]):
            print(
                f"  [{i}] id={s.section_id} title={s.title[:40] if s.title else 'N/A'} bc={list(s.breadcrumb[:2]) if s.breadcrumb else []}"
            )
    await redis.aclose()


asyncio.run(test())
