import asyncio, pathlib
from app.modules.documents.ingestion.ingestion_service import IngestionService
from app.core.db import async_engine, async_session
from app.modules.documents.repositories import SectionRepository

async def main():
    p = pathlib.Path('test_tailieukythuat.md')
    if not p.is_file():
        print('test file missing')
        return
    content = p.read_bytes()
    async with async_engine.begin() as conn:
        async with async_session(bind=conn) as session:
            service = IngestionService(redis_client=None, db_session=session, section_repo=SectionRepository(session))
            result = await service.ingest(p.name, content, user_id='test', document_id='test-doc')
            print('Result:', result)

asyncio.run(main())
