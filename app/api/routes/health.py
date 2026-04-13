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
        pass
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
        pass

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
        pass

    return None



def _build_snapshot(selected_document_id: str | None = None) -> dict[str, Any]:
    payload = build_health_payload()
    docs = _fetch_documents()
    active_docs = sum(1 for d in docs if d.deleted_at is None)
    latest_document_id = str(docs[0].id) if docs else None
    target_document_id = selected_document_id or latest_document_id

    return {
        "status": payload.get("status", "unknown"),
        "timestamp": datetime.now(UTC).isoformat(),
        "active_docs": active_docs,
        "total_docs": len(docs),
        "latest_document_id": latest_document_id or "",
        "target_document_id": target_document_id or "",
        "checks": payload.get("checks", {}),
        "services_html": _services_rows(payload),
    }


def _render_page(snapshot: dict[str, Any]) -> str:
    prefix = settings.api_v1_prefix.rstrip("/")
    return f"""
<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>Service Health Monitoring</title>
  <style>
    body {{ font-family: sans-serif; margin: 16px; background-color: #f8fafc; color: #334155; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 600px; margin-bottom: 16px; background: white; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: left; }}
    th {{ background: #f1f5f9; }}
    h1, h2 {{ margin: 8px 0; color: #0f172a; }}
    .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; color: white; }}
    .up {{ background: #22c55e; }}
    .down {{ background: #ef4444; }}
    .degraded {{ background: #f59e0b; }}
    .container {{ background: white; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; max-width: 800px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .info-box {{ background: #e0f2fe; padding: 12px; border-radius: 4px; margin-top: 20px; font-size: 14px; border: 1px solid #bae6fd; }}
  </style>
  <script>
    async function refreshData() {{
      try {{
        const res = await fetch('{prefix}/health/data');
        const data = await res.json();
        document.getElementById('status').textContent = data.status;
        document.getElementById('ts').textContent = data.timestamp;
        
        // Cập nhật lại HTML cho bảng Services
        const tbody = document.getElementById('services-body');
        let newHtml = '';
        const checks = data.checks || {{}};
        for (const [name, check] of Object.entries(checks)) {{
            let statusClass = check.status === 'up' ? 'up' : (check.status === 'down' ? 'down' : 'degraded');
            newHtml += `<tr>
                <td>${{name}}</td>
                <td><span class="badge ${{statusClass}}">${{check.status}}</span></td>
            </tr>`;
        }}
        tbody.innerHTML = newHtml;
      }} catch (e) {{
        console.error(e);
      }}
    }}
    setInterval(refreshData, 5000);
  </script>
</head>
<body>
  <div class="container">
      <h1>🩺 Service Health Monitor</h1>
      <p>Overall Status: <strong id='status'>{html.escape(str(snapshot['status']).upper())}</strong></p>
      <p>Last checked: <span id='ts'>{html.escape(str(snapshot['timestamp']))}</span></p>
      <p><a href="/" style="color: #3b82f6;">← Về trang Admin Dashboard</a></p>

      <h2>Core Services</h2>
      <table>
        <thead><tr><th>Service Name</th><th>Status</th></tr></thead>
        <tbody id='services-body'>{snapshot['services_html']}</tbody>
      </table>

      <div class="info-box">
          <strong>💡 Hướng dẫn Restart Service đang lỗi:</strong><br><br>
          Hiện tại API không có quyền thực thi lệnh docker (vì lý do bảo mật). Để khởi động lại dịch vụ bị lỗi (Ví dụ <code>redis</code> báo DOWN), hãy SSH vào server và chạy lệnh sau:<br><br>
          <code>docker compose restart [tên-service]</code><br><br>
          Ví dụ: <code>docker compose restart redis</code> hoặc <code>docker compose restart worker</code>
      </div>
  </div>
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
    """JSON-only: list Qdrant nodes for a document. HTML rendering moved to /view/nodes."""
    document_id = request.query_params.get("document_id") or ""
    points = _fetch_qdrant_nodes(document_id=document_id, limit=300)
    return {
        "document_id": document_id,
        "count": len(points),
        "points": points,
    }


@router.get("/health/node")
async def health_node(request: Request):
    """JSON-only: get a single Qdrant node. HTML rendering moved to /view/node."""
    document_id = request.query_params.get("document_id") or ""
    node_id = request.query_params.get("node_id") or ""
    point = _fetch_qdrant_node(document_id=document_id, node_id=node_id)
    return {
        "document_id": document_id,
        "node_id": node_id,
        "found": point is not None,
        "point": point,
    }