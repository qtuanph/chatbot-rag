from datetime import datetime, timezone

from sqlalchemy import delete

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.core import Document, DocNode
from app.services.ingestion import extract_nodes
from app.services.storage import build_storage


@celery_app.task(name="app.worker.parse_document_task", bind=True)
def parse_document_task(self, task_id: str, document_id: str, file_path: str) -> dict[str, str]:
    storage = build_storage()
    self.update_state(
        task_id=task_id,
        state="STARTED",
        meta={"stage": "download", "progress": {"step": "download", "percent": 10}, "document_id": document_id},
    )
    content = storage.download_bytes(file_path)

    filename = file_path.rsplit("/", 1)[-1]
    self.update_state(
        task_id=task_id,
        state="STARTED",
        meta={"stage": "parse", "progress": {"step": "parse", "percent": 40}, "document_id": document_id},
    )
    nodes = extract_nodes(filename, content)

    self.update_state(
        task_id=task_id,
        state="STARTED",
        meta={"stage": "index", "progress": {"step": "index", "percent": 75}, "document_id": document_id},
    )

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise ValueError(f"Document not found: {document_id}")

        document.status = "processing"
        session.commit()

        session.execute(delete(DocNode).where(DocNode.document_id == document_id))

        root = DocNode(
            document_id=document.id,
            heading="Document",
            full_text="",
            summary=None,
            level=0,
            order_index=0,
        )
        session.add(root)
        session.flush()

        heading_to_id = {"Document": root.id}
        created_nodes = 1

        for node in nodes:
            if node.level == 0 and node.heading == "Document":
                continue

            parent_id = heading_to_id.get(node.parent_ref or "Document", root.id)
            new_node = DocNode(
                document_id=document.id,
                parent_id=parent_id,
                heading=node.heading,
                full_text=node.full_text,
                summary=node.summary,
                page_range=node.page_range,
                level=node.level,
                order_index=node.order_index,
            )
            session.add(new_node)
            session.flush()
            heading_to_id[node.heading] = new_node.id
            created_nodes += 1

        document.status = "ready"
        document.updated_at = datetime.now(timezone.utc)

        session.commit()

    result = {
        "task_id": task_id,
        "document_id": document_id,
        "file_path": file_path,
        "status": "ready",
        "stage": "done",
        "progress": {"step": "done", "percent": 100},
        "bytes": len(content),
        "node_count": created_nodes,
    }

    return result
