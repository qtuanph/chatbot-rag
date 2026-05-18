# PLAN: Replace CLIProxyAPI → 9Router

## Tổng quan

Thay thế CLIProxyAPI (Go proxy, port 8317) bằng **9Router** (Next.js 16 AI router, port 2908).
Provider management chuyển từ FastAPI admin CRUD sang **9Router Dashboard** tại `http://localhost:2908`.

## Kiến trúc mới

```
Browser (Next.js webapp)
  └── /api/bep/* → FastAPI Backend
        │
  FastAPI ChatService → LlamaIndex OpenAI LLM (api_base=ai-proxy:2908/v1)
                                      ↓
                           9Router (Next.js 16 — Docker)
                         port 2908 (API + Dashboard)
                                      ↓
                     Kiro · Claude · Gemini · OpenCode Free
                     (config qua Dashboard)
```

## Container thay đổi

| Service | Trạng thái | Details |
|---------|-----------|---------|
| **ai-proxy** | **THAY** | `decolua/9router:latest` thay `eceasy/cli-proxy-api:latest`, port 8317→2908 |
| api | SỬA | dependency healthcheck `service_started` → `service_healthy` |
| **ai-proxy healthcheck** | **MỚI** | wget tới `/api/health` trên port 2908 |

## File changed

| Thể loại | File | Hành động |
|----------|------|-----------|
| Docker | docker-compose.yml | Sửa ai-proxy service + volume |
| Docker | ops/entrypoint-ai-proxy.sh | **XOÁ** — không cần |
| Config | .env | CLIPROXY_* → AI_PROXY_* |
| Config | app/core/config.py | Sửa settings + get_settings() |
| Adapter | app/adapters/ai/cliproxy_bridge.py | **RENAME** → proxy_bridge.py |
| Adapter | app/adapters/ai/__init__.py | Sửa import |
| Admin | app/modules/admin/router.py | Đơn giản hoá (chỉ còn /admin/models) |
| Admin | app/modules/admin/schemas.py | Xoá provider schemas |
| Admin | app/modules/admin/services/model_provider_service.py | **XOÁ** |
| Admin | app/modules/admin/services/__init__.py | **XOÁ** |
| Chat | app/modules/chat/services/service.py | Import sửa |
| Chat | app/modules/chat/tasks/memory_tasks.py | Import sửa |
| Chat | app/modules/chat/services/user_memory_service.py | Import sửa |
| Chat | app/modules/chat/services/query_refiner.py | Import sửa |
| Chat | app/modules/chat/retrieval/expansion_service.py | Import sửa |
| Analytics | app/modules/analytics/ragas_evaluator.py | Import sửa |
| Analytics | app/modules/analytics/service.py | Sửa model name |
| System | app/modules/system/service.py | Sửa provider label |
| Docs | README.md | ~10 mục |
| Docs | AGENTS.md | ~3 mục |
| Docs | PLAN.md | **GHI ĐÈ** |
| Docs | docs/1_ARCHITECTURE.md | ~5 mục |
| Docs | docs/3_API_CONTRACTS.md | ~3 mục |
| Docs | docs/4_DEPLOYMENT.md | ~3 mục |
| Docs | docs/0_QUICK_REFERENCE.json | ~3 mục |

## Env vars mới

```env
AI_PROXY_URL=http://ai-proxy:2908
AI_PROXY_DEFAULT_MODEL=
AI_PROXY_JWT_SECRET=...
AI_PROXY_INITIAL_PASSWORD=123456
```

## Key notes

1. **9Router không cần API key** — `REQUIRE_API_KEY: "false"`, không gửi Bearer header
2. **Provider config** — quản lý qua Dashboard port 2908, không qua FastAPI
3. **Model naming** — 9Router dùng format `prefix/model` (vd: `kr/claude-sonnet-4.5`)
4. **Volume** — `9router-data:/app/data` lưu SQLite database của 9Router
5. **Dashboard + API chung 1 port** — 2908 cho cả UI và `/v1/*` endpoints
