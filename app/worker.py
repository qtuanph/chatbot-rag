from datetime import datetime, timezone

from sqlalchemy import delete

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Document, DocNode
from app.services.ingestion import extract_nodes_with_artifact
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
    nodes, artifact = extract_nodes_with_artifact(filename, content)

    self.update_state(
        task_id=task_id,
        state="STARTED",
        meta={"stage": "index", "progress": {"step": "index", "percent": 75}, "document_id": document_id},
    )

    created_nodes = 0
    try:
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is None:
                raise ValueError(f"Document not found: {document_id}")

            document.status = "processing"
            document.parse_error = None

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

            ref_to_id = {"root": root.id}
            created_nodes = 1

            for node in nodes:
                parent_ref = node.parent_ref or "root"
                if parent_ref not in ref_to_id:
                    raise ValueError(f"Invalid parent_ref '{parent_ref}' for node '{node.ref}'")

                new_node = DocNode(
                    document_id=document.id,
                    parent_id=ref_to_id[parent_ref],
                    heading=node.heading,
                    full_text=node.full_text,
                    summary=node.summary,
                    page_range=node.page_range,
                    level=node.level,
                    order_index=node.order_index,
                )
                session.add(new_node)
                session.flush()
                ref_to_id[node.ref] = new_node.id
                created_nodes += 1

            if artifact.non_empty_node_count < settings.ingestion_min_non_empty_nodes:
                raise ValueError(
                    "Extraction quality too low: non_empty_node_count "
                    f"{artifact.non_empty_node_count} < {settings.ingestion_min_non_empty_nodes}"
                )
            if artifact.total_text_chars < settings.ingestion_min_total_text_chars:
                raise ValueError(
                    "Extraction quality too low: total_text_chars "
                    f"{artifact.total_text_chars} < {settings.ingestion_min_total_text_chars}"
                )

            metadata = dict(document.extra_metadata or {})
            artifact_payload = artifact.to_dict()
            artifact_payload["node_manifest"] = [
                {
                    "ref": node.ref,
                    "heading": node.heading,
                    "level": node.level,
                    "parent_ref": node.parent_ref,
                    "page_range": node.page_range,
                    "text_chars": len(node.full_text or ""),
                    "summary": (node.summary or node.full_text[:120])[:120],
                }
                for node in nodes[:200]
            ]
            artifact_payload["node_manifest_truncated"] = len(nodes) > 200
            artifact_payload["node_manifest_count"] = len(nodes)
            metadata["ingestion_artifact"] = artifact_payload
            document.extra_metadata = metadata

            document.status = "ready"
            document.updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as exc:
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is not None:
                document.status = "failed"
                document.parse_error = str(exc)[:2000]
                document.updated_at = datetime.now(timezone.utc)
                session.commit()
        raise

    result = {
        "task_id": task_id,
        "document_id": document_id,
        "file_path": file_path,
        "status": "ready",
        "stage": "done",
        "progress": {"step": "done", "percent": 100},
        "bytes": len(content),
        "node_count": created_nodes,
        "ingestion_artifact": metadata.get("ingestion_artifact") if 'metadata' in locals() else artifact.to_dict(),
    }

    return result
