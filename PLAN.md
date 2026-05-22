# PLAN: Dynamic AI Provider Management

## Mục tiêu

Thay thế 3 bộ kết nối AI (Embedding, Reranker, LLM) từ `.env`/`config.py` sang **SQLite** + **Admin UI**, cho phép admin thay đổi provider mà không cần rebuild/deploy.

## Kiến trúc

```
┌──────────────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  Frontend            │     │  Backend (FastAPI)   │     │  Storage     │
│  /admin/providers    │────▶│  /api/v1/settings/*  │────▶│  SQLite      │
│  - 3 tabs            │     │                      │     │  settings.db │
│  - Provider CRUD     │     │  RuntimeProviderMgr  │◀────│  (volume)    │
│  - API key manager   │     │  (override Settings) │     └──────────────┘
│  - Templates         │     └─────────────────────┘            │
└──────────────────────┘                                       ▼
                                                        config.py fallback
                                                        (nếu SQLite rỗng)
```

## Phases

### Phase 1: Backend — SQLite + Provider Management

**New module: `app/modules/settings/`**

| File | Purpose |
|------|---------|
| `__init__.py` | Re-export |
| `database.py` | SQLite engine + init + seed templates |
| `models.py` | SQLAlchemy models |
| `repository.py` | CRUD operations |
| `service.py` | Business logic + template definitions |
| `router.py` | FastAPI endpoints |
| `runtime_manager.py` | Singleton — override LlamaIndex Settings at runtime |
| `schemas.py` | Pydantic request/response schemas |

**SQLite Tables:**

```sql
ai_providers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  service_type TEXT NOT NULL,         -- "embedding" | "reranker" | "llm"
  provider_name TEXT NOT NULL,        -- "tei" | "openai" | "nvidia" | ...
  display_name TEXT NOT NULL,
  url TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT '',
  api_key TEXT DEFAULT '',
  is_active INTEGER DEFAULT 0,       -- only one active per service_type
  is_builtin INTEGER DEFAULT 0,       -- TEI local = builtin, can't delete
  priority INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id INTEGER NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
  key_value TEXT NOT NULL,
  is_active INTEGER DEFAULT 1,
  failure_count INTEGER DEFAULT 0,
  last_used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Pre-built Templates (seeded on first init):**

| Service | Provider | URL | Model | Builtin |
|---------|----------|-----|-------|---------|
| embedding | TEI | `http://ai-embedding:80/v1` | `gte-multilingual-base` | ✅ |
| embedding | OpenAI | `https://api.openai.com/v1` | `text-embedding-ada-002` | |
| embedding | OpenRouter | `https://openrouter.ai/api/v1` | `openai/text-embedding-3-small` | |
| embedding | NVIDIA NIM | `https://ai.api.nvidia.com/v1` | `nvidia/nv-embed-qa-4` | |
| embedding | Google Gemini | `https://generativelanguage.googleapis.com/v1` | `text-embedding-004` | |
| embedding | Cohere | `https://api.cohere.com/v1` | `embed-multilingual-v3.0` | |
| reranker | TEI | `http://ai-reranker:80` | `gte-multilingual-reranker-base` | ✅ |
| reranker | NVIDIA NIM | `https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking` | `llama-nemotron-rerank-vl-1b-v2` | |
| reranker | Cohere | `https://api.cohere.com` | `rerank-multilingual-v3.0` | |
| llm | 9Router | `http://ai-proxy:2908/v1` | `chatbot-rag` | ✅ |

**API Endpoints:**

```
GET    /api/v1/settings/providers?service_type=embedding   → list providers
POST   /api/v1/settings/providers                          → create provider
PUT    /api/v1/settings/providers/{id}                     → update provider
DELETE /api/v1/settings/providers/{id}                     → delete provider
POST   /api/v1/settings/providers/{id}/activate            → set active
POST   /api/v1/settings/providers/{id}/test                → test connection
GET    /api/v1/settings/providers/{id}/keys                → list API keys
POST   /api/v1/settings/providers/{id}/keys                → add API key
DELETE /api/v1/settings/providers/{id}/keys/{key_id}       → delete API key
GET    /api/v1/settings/templates                          → list templates
```

### Phase 1: Backend — Runtime Integration

**`RuntimeProviderManager`** singleton:
- `get_active(service_type)` → lấy active provider từ SQLite
- `get_next_key(provider_id)` → round-robin API keys
- `apply()` → rebuild `Settings.embed_model` / ghi đè `init_llama_index()`
- `reload()` → force refresh from SQLite

**Modify `init_llama_index()`:**
1. Load defaults từ `config.py` như hiện tại
2. Gọi `RuntimeProviderManager.apply()` → nếu SQLite có active provider, override `Settings.embed_model`
3. Reranker vẫn dùng `get_reranker()` nhưng thay vì đọc từ `settings.*`, đọc từ SQLite active provider
4. LLM provider (9Router) builtin — chỉ thay đổi qua SQLite sau này

**Volume mount:** Thêm `settings-data:/app/data` cho api + workers services.

### Phase 1: Frontend — Providers Page

**Thay thế `admin/providers/page.tsx`** (đang `return null`).

Components:
| File | Purpose |
|------|---------|
| `admin/providers/page.tsx` | Main page — 3 tabs + layout |
| `admin/providers/_provider-list.tsx` | List of providers for a service |
| `admin/providers/_provider-card.tsx` | Single provider card |
| `admin/providers/_provider-form.tsx` | Add/edit dialog |
| `admin/providers/_template-picker.tsx` | Pick from templates on create |
| `admin/providers/_api-key-manager.tsx` | Manage multiple API keys |

**Sidebar:** "Kết nối AI" → expandable, 3 sub-items: Embedding, Reranker, LLM.

### Phase 2: Loại bỏ khỏi .env

Sau khi SQLite hoạt động, xóa khỏi `.env`:
- `EMBEDDING_API_BASE`, `EMBEDDING_API_KEY`, `EMBEDDING_HF_MODEL`
- `RERANKER_BACKEND`, `NVIDIA_API_KEY`, `NVIDIA_RERANKER_MODEL`, `NVIDIA_RERANKER_URL`

Các field tương ứng trong `config.py` giữ default để fallback.

## Implementation Status ✅

### Backend — Complete
| # | Item | Status |
|---|------|--------|
| 1 | `database.py` — SQLite engine + seed templates | ✅ |
| 2 | `repository.py` — CRUD for providers & api_keys | ✅ |
| 3 | `schemas.py` — Pydantic schemas | ✅ |
| 4 | `service.py` — Business logic + templates + test endpoint | ✅ |
| 5 | `router.py` — API endpoints (9 endpoints) | ✅ |
| 6 | Register router in `app/main.py` | ✅ |
| 7 | `runtime_manager.py` — Override LlamaIndex Settings | ✅ |
| 8 | Modify `app/core/llama_index.py` — call RuntimeProviderManager | ✅ |
| 9 | Modify `app/adapters/reranker/__init__.py` — read from SQLite | ✅ |
| 10 | Modify TEI/NVIDIA postprocessors — accept params from caller | ✅ |
| 11 | Docker: `settings-data` volume + `/app/data` dir in Dockerfile | ✅ |
| 12 | Entrypoint scripts: auto-init DB on container start | ✅ |
| 13 | Remove embedding/reranker/LLM config from `.env` | ✅ |

### Frontend — Complete
| # | Item | Status |
|---|------|--------|
| 14 | `admin/providers/page.tsx` — 3-tab page with CRUD | ✅ |
| 15 | `lib/api-client.ts` — `settingsApi` module | ✅ |
| 16 | `types/api.ts` — AIProvider, ApiKeyItem, Template types | ✅ |
| 17 | `app-sidebar.tsx` — collapsible sub-items for "Kết nối AI" | ✅ |

### Files Created
```
app/modules/settings/
  __init__.py
  database.py          — SQLite engine + seed
  schemas.py           — Pydantic schemas
  repository.py        — CRUD
  service.py           — Business logic + templates
  router.py            — API endpoints
  runtime_manager.py   — LlamaIndex override singleton

webapp/app/(main)/admin/providers/page.tsx   — Full providers page
webapp/types/api.ts                          — Added AIProvider types
webapp/lib/api-client.ts                     — Added settingsApi
webapp/components/app-sidebar.tsx            — Collapsible sub-items
```

### Files Modified
```
app/core/llama_index.py              — Added RuntimeProviderManager call
app/adapters/reranker/__init__.py    — Read from SQLite
app/adapters/reranker/tei_postprocessor.py   — base_url field
app/adapters/reranker/nvidia_postprocessor.py — base_url/model/key fields
app/main.py                          — Register settings router
Dockerfile                           — Create /app/data
docker-compose.yml                   — settings-data volume
ops/entrypoint-api.sh                — init_db on start
ops/entrypoint-worker.sh             — init_db on start
.env                                 — Removed embedding/reranker/LLM vars
.env.example                         — Updated docs
docs/7_CURRENT_SETTINGS.json         — Updated docs
```
