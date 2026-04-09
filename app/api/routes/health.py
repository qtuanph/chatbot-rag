from datetime import UTC, datetime
import html
from typing import Any
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Document
from app.services.health import build_health_payload
from app.services.storage import build_storage

router = APIRouter(tags=["health"])


def _fetch_documents(limit: int = 100) -> list[Document]:
    try:
        with SessionLocal() as session:
            return (
                session.query(Document)
                .order_by(Document.created_at.desc())
                .limit(limit)
                .all()
            )
    except Exception:
        return []


def _fetch_storage_objects() -> list[dict[str, Any]]:
    try:
        storage = build_storage()
        if hasattr(storage, "list_objects"):
            objects = storage.list_objects()
            if isinstance(objects, list):
                return objects
    except Exception:
        return []
    return []


def _services_rows(payload: dict[str, Any]) -> str:
    checks = payload.get("checks", {})
    if not isinstance(checks, dict) or not checks:
        return "<tr><td colspan='2'>No service data</td></tr>"

    rows: list[str] = []
    for name, value in checks.items():
        status_text = "unknown"
        if isinstance(value, dict):
            status_text = str(value.get("status", "unknown"))
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(name))}</td>"
            f"<td>{html.escape(status_text)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _pipeline_rows(docs: list[Document]) -> str:
    if not docs:
        return "<tr><td colspan='6'>No documents</td></tr>"

    rows: list[str] = []
    for doc in docs:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(doc.id)[:8])}</td>"
            f"<td>{html.escape(doc.file_name)}</td>"
            f"<td>{html.escape(doc.status)}</td>"
            f"<td>{html.escape(doc.status_stage)}</td>"
            f"<td>{int(doc.progress_percent)}%</td>"
            f"<td>{doc.file_size // 1024} KB</td>"
            "</tr>"
        )
    return "".join(rows)


def _storage_rows(objects: list[dict[str, Any]]) -> str:
    if not objects:
        return "<tr><td colspan='4'>No files</td></tr>"

    rows: list[str] = []
    for obj in objects:
        doc_id = str(obj.get("document_id", ""))
        filename = str(obj.get("filename", ""))
        size = int(obj.get("size", 0))
        modified = str(obj.get("last_modified", ""))
        rows.append(
            "<tr>"
            f"<td>{html.escape(doc_id[:8])}</td>"
            f"<td>{html.escape(filename)}</td>"
            f"<td>{size // 1024} KB</td>"
            f"<td>{html.escape(modified[:19])}</td>"
            "</tr>"
        )
    return "".join(rows)


def _fetch_qdrant_nodes(document_id: str | None, limit: int = 30) -> list[dict[str, Any]]:
    if not document_id:
        return []

    body: dict[str, Any] = {
        "with_payload": True,
        "with_vector": False,
        "limit": limit,
        "filter": {
            "must": [
                {
                    "key": "document_id",
                    "match": {"value": document_id},
                }
            ]
        },
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.post(
                f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/scroll",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result", {}) if isinstance(data, dict) else {}
            points = result.get("points", []) if isinstance(result, dict) else []
            if isinstance(points, list):
                return points
    except Exception:
        return []

    return []


def _fetch_qdrant_node(document_id: str, node_id: str) -> dict[str, Any] | None:
    if not document_id or not node_id:
        return None

    body: dict[str, Any] = {
        "with_payload": True,
        "with_vector": False,
        "limit": 1,
        "filter": {
            "must": [
                {"key": "document_id", "match": {"value": document_id}},
                {"key": "node_id", "match": {"value": node_id}},
            ]
        },
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.post(
                f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/scroll",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result", {}) if isinstance(data, dict) else {}
            points = result.get("points", []) if isinstance(result, dict) else []
            if isinstance(points, list) and points:
                return points[0]
    except Exception:
        return None

    return None


def _nodes_rows(points: list[dict[str, Any]]) -> str:
    if not points:
        return "<tr><td colspan='9'>No nodes found in Qdrant</td></tr>"

    rows: list[str] = []
    prefix = settings.api_v1_prefix.rstrip("/")
    for point in points:
        payload = point.get("payload", {}) if isinstance(point, dict) else {}
        node_id = str(payload.get("node_id", ""))
        document_id = str(payload.get("document_id", ""))
        node_type = str(payload.get("node_type", ""))
        section = str(payload.get("section_title", ""))
        page = str(payload.get("page_number", ""))
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        text = str(payload.get("text", "")).replace("\n", " ").strip()
        text_length = len(str(payload.get("text", "")))
        if len(text) > 200:
            text = text[:200] + "..."

        rows.append(
            "<tr>"
            f"<td>{html.escape(document_id[:8])}</td>"
            f"<td>{html.escape(node_id[:8])}</td>"
            f"<td>{html.escape(node_type)}</td>"
            f"<td>{html.escape(section)}</td>"
            f"<td>{html.escape(page)}</td>"
            f"<td>{text_length}</td>"
            f"<td>{html.escape(text)}</td>"
            f"<td><pre style='margin:0; white-space:pre-wrap;'>{html.escape(metadata_json)}</pre></td>"
            f"<td><a href='{prefix}/health/node?document_id={html.escape(document_id)}&node_id={html.escape(node_id)}'>Show node</a></td>"
            "</tr>"
        )
    return "".join(rows)


def _render_nodes_page(document_id: str, points: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    prefix = settings.api_v1_prefix.rstrip("/")
    for point in points:
        payload = point.get("payload", {}) if isinstance(point, dict) else {}
        node_id = str(payload.get("node_id", ""))
        node_type = str(payload.get("node_type", ""))
        section = str(payload.get("section_title", ""))
        page = str(payload.get("page_number", ""))
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        text = str(payload.get("text", "")).replace("\n", " ").strip()
        text_length = len(str(payload.get("text", "")))
        rows.append(
            "<tr>"
            f"<td>{html.escape(node_id)}</td>"
            f"<td>{html.escape(node_type)}</td>"
            f"<td>{html.escape(section)}</td>"
            f"<td>{html.escape(page)}</td>"
            f"<td>{text_length}</td>"
            f"<td>{html.escape(text)}</td>"
            f"<td><pre style='margin:0; white-space:pre-wrap;'>{html.escape(metadata_json)}</pre></td>"
            f"<td><a href='{prefix}/health/node?document_id={html.escape(document_id)}&node_id={html.escape(node_id)}'>Show node</a></td>"
            "</tr>"
        )

    body_html = "".join(rows) if rows else "<tr><td colspan='8'>No nodes found</td></tr>"
    return f"""
<!doctype html>
<html>
<head>
    <meta charset='utf-8'/>
    <meta name='viewport' content='width=device-width, initial-scale=1'/>
    <title>All Nodes</title>
    <style>
        body {{ font-family: sans-serif; margin: 16px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ccc; padding: 6px; text-align: left; vertical-align: top; }}
    </style>
</head>
<body>
    <h1>All Nodes</h1>
    <p>Document ID: <strong>{html.escape(document_id)}</strong></p>
    <p><a href='{prefix}/health?document_id={html.escape(document_id)}'>Back to health</a></p>
    <table>
        <thead><tr><th>Node ID</th><th>Type</th><th>Section</th><th>Page</th><th>Text Length</th><th>Text</th><th>Metadata (JSON)</th><th>Action</th></tr></thead>
        <tbody>{body_html}</tbody>
    </table>
</body>
</html>
"""


def _render_node_page(document_id: str, node_id: str, point: dict[str, Any] | None) -> str:
    payload = point.get("payload", {}) if isinstance(point, dict) else {}
    node_type = str(payload.get("node_type", ""))
    section = str(payload.get("section_title", ""))
    page = str(payload.get("page_number", ""))
    parent_id = str(payload.get("parent_id", ""))
    order = str(payload.get("order", ""))
    text = str(payload.get("text", ""))
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    text_length = len(text)
    prefix = settings.api_v1_prefix.rstrip("/")

    if not point:
        return f"""
<!doctype html>
<html><body>
<h1>Node not found</h1>
<p>document_id={html.escape(document_id)} node_id={html.escape(node_id)}</p>
<p><a href='{prefix}/health/nodes?document_id={html.escape(document_id)}'>Back to all nodes</a></p>
</body></html>
"""

    return f"""
<!doctype html>
<html>
<head>
    <meta charset='utf-8'/>
    <meta name='viewport' content='width=device-width, initial-scale=1'/>
    <title>Node Detail</title>
    <style>
        body {{ font-family: sans-serif; margin: 16px; }}
        pre {{ white-space: pre-wrap; border: 1px solid #ccc; padding: 10px; }}
        table {{ border-collapse: collapse; }}
        td, th {{ border: 1px solid #ccc; padding: 6px; text-align: left; }}
    </style>
</head>
<body>
    <h1>Node Detail</h1>
    <p><a href='{prefix}/health/nodes?document_id={html.escape(document_id)}'>Back to all nodes</a></p>
    <table>
        <tr><th>Document ID</th><td>{html.escape(document_id)}</td></tr>
        <tr><th>Node ID</th><td>{html.escape(node_id)}</td></tr>
        <tr><th>Type</th><td>{html.escape(node_type)}</td></tr>
        <tr><th>Section</th><td>{html.escape(section)}</td></tr>
        <tr><th>Page</th><td>{html.escape(page)}</td></tr>
        <tr><th>Parent</th><td>{html.escape(parent_id)}</td></tr>
        <tr><th>Order</th><td>{html.escape(order)}</td></tr>
        <tr><th>Text Length</th><td>{text_length}</td></tr>
        <tr><th>Metadata</th><td><pre>{html.escape(metadata_json)}</pre></td></tr>
    </table>
    <h2>Text</h2>
    <pre>{html.escape(text)}</pre>
</body>
</html>
"""


def _build_snapshot(selected_document_id: str | None = None) -> dict[str, Any]:
    payload = build_health_payload()
    docs = _fetch_documents()
    objects = _fetch_storage_objects()
    active_docs = sum(1 for d in docs if d.deleted_at is None)
    latest_document_id = str(docs[0].id) if docs else None
    target_document_id = selected_document_id or latest_document_id
    points = _fetch_qdrant_nodes(target_document_id)

    return {
        "status": payload.get("status", "unknown"),
        "timestamp": datetime.now(UTC).isoformat(),
        "active_docs": active_docs,
        "total_docs": len(docs),
        "latest_document_id": latest_document_id or "",
        "target_document_id": target_document_id or "",
        "nodes_preview_count": len(points),
        "checks": payload.get("checks", {}),
        "services_html": _services_rows(payload),
        "pipeline_html": _pipeline_rows(docs),
        "storage_html": _storage_rows(objects),
        "nodes_html": _nodes_rows(points),
    }


def _render_page(snapshot: dict[str, Any]) -> str:
    prefix = settings.api_v1_prefix.rstrip("/")
    return f"""
<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>Health Monitor</title>
  <style>
    body {{ font-family: sans-serif; margin: 16px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px; text-align: left; }}
    h1, h2 {{ margin: 8px 0; }}
  </style>
  <script>
    async function refreshData() {{
      try {{
                const docInput = document.getElementById('document_id');
                const selectedDoc = docInput ? encodeURIComponent(docInput.value || '') : '';
                const res = await fetch('{prefix}/health/data?document_id=' + selectedDoc);
        const data = await res.json();
        document.getElementById('status').textContent = data.status;
        document.getElementById('ts').textContent = data.timestamp;
        document.getElementById('active').textContent = data.active_docs;
        document.getElementById('total').textContent = data.total_docs;
        document.getElementById('nodes-doc').textContent = data.target_document_id || '-';
                document.getElementById('nodes-count').textContent = data.nodes_preview_count;
        document.getElementById('services-body').innerHTML = data.services_html;
        document.getElementById('pipeline-body').innerHTML = data.pipeline_html;
        document.getElementById('storage-body').innerHTML = data.storage_html;
                document.getElementById('nodes-body').innerHTML = data.nodes_html;
      }} catch (e) {{
        console.error(e);
      }}
    }}
    setInterval(refreshData, 5000);
  </script>
</head>
<body>
  <h1>Health Monitor</h1>
  <p>Status: <strong id='status'>{html.escape(str(snapshot['status']))}</strong></p>
  <p>Updated: <span id='ts'>{html.escape(str(snapshot['timestamp']))}</span></p>
  <p>Documents: <span id='active'>{snapshot['active_docs']}</span> active / <span id='total'>{snapshot['total_docs']}</span> total</p>

  <h2>Services</h2>
  <table>
    <thead><tr><th>Name</th><th>Status</th></tr></thead>
    <tbody id='services-body'>{snapshot['services_html']}</tbody>
  </table>

  <h2>Pipeline</h2>
  <table>
    <thead><tr><th>ID</th><th>File</th><th>Status</th><th>Stage</th><th>Progress</th><th>Size</th></tr></thead>
    <tbody id='pipeline-body'>{snapshot['pipeline_html']}</tbody>
  </table>

  <h2>Storage</h2>
  <table>
    <thead><tr><th>Doc ID</th><th>Filename</th><th>Size</th><th>Last Modified</th></tr></thead>
    <tbody id='storage-body'>{snapshot['storage_html']}</tbody>
  </table>

    <h2>Qdrant Nodes Preview</h2>
    <form method='get' action='{prefix}/health' style='margin-bottom:8px;'>
        <label for='document_id'>Document ID (optional):</label>
        <input id='document_id' name='document_id' type='text' value='{html.escape(str(snapshot.get("target_document_id", "")))}' style='min-width:360px;' />
        <button type='submit'>Inspect</button>
    </form>
    <form method='get' action='{prefix}/health/node' style='margin-bottom:8px;'>
        <input name='document_id' type='hidden' value='{html.escape(str(snapshot.get("target_document_id", "")))}' />
        <label for='node_id'>Node ID:</label>
        <input id='node_id' name='node_id' type='text' value='' style='min-width:360px;' />
        <button type='submit'>Show 1 node</button>
    </form>
    <p>Inspecting document: <strong id='nodes-doc'>{html.escape(str(snapshot['target_document_id'])) or '-'}</strong> | Nodes shown: <strong id='nodes-count'>{snapshot['nodes_preview_count']}</strong></p>
    <p><a href='{prefix}/health/nodes?document_id={html.escape(str(snapshot['target_document_id']))}'>Show all nodes</a></p>
    <table>
        <thead><tr><th>Doc ID</th><th>Node ID</th><th>Type</th><th>Section</th><th>Page</th><th>Text Length</th><th>Text Preview</th><th>Metadata (JSON)</th><th>Action</th></tr></thead>
        <tbody id='nodes-body'>{snapshot['nodes_html']}</tbody>
    </table>
</body>
</html>
"""


@router.get("/health")
async def healthcheck(request: Request):
    selected_document_id = request.query_params.get("document_id")
    snapshot = _build_snapshot(selected_document_id=selected_document_id)
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(_render_page(snapshot))
    return snapshot


@router.get("/health/data")
async def health_data(request: Request):
    selected_document_id = request.query_params.get("document_id")
    return _build_snapshot(selected_document_id=selected_document_id)


@router.get("/health/nodes")
async def health_nodes(request: Request):
    document_id = request.query_params.get("document_id") or ""
    points = _fetch_qdrant_nodes(document_id=document_id, limit=300)
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(_render_nodes_page(document_id=document_id, points=points))
    return {
        "document_id": document_id,
        "count": len(points),
        "points": points,
    }


@router.get("/health/node")
async def health_node(request: Request):
    document_id = request.query_params.get("document_id") or ""
    node_id = request.query_params.get("node_id") or ""
    point = _fetch_qdrant_node(document_id=document_id, node_id=node_id)
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(_render_node_page(document_id=document_id, node_id=node_id, point=point))
    return {
        "document_id": document_id,
        "node_id": node_id,
        "found": point is not None,
        "point": point,
    }