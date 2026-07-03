# Agent Guardrails

## Docs First (Bắt buộc đọc theo thứ tự)

| Priority | File | Purpose |
|----------|------|---------|
| 0 | `docs/0_QUICK_REFERENCE.json` | Cheat sheet ngắn — rules, env, data map, anti-patterns |
| 1 | `docs/1_ARCHITECTURE.md` | Kiến trúc hiện tại, domain model, storage, CSR, delete order |
| 2 | `docs/2_WORKFLOWS.json` | Chỉ mục workflow |
| 2.1 | `docs/2.1_WORKFLOWS_INGESTION.md` | Upload → parse → chunk → embed → index |
| 2.2 | `docs/2.2_WORKFLOWS_CHAT.md` | Chat stateless, retrieval, streaming |
| 2.3 | `docs/2.3_WORKFLOWS_DELETE.md` | Hard delete workflow |
| 2.4 | `docs/2.4_WORKFLOWS_AUDIT.md` | Audit logging |
| 2.5 | `docs/2.5_WORKFLOWS_ANALYTICS.md` | Usage, quota, cost analytics |
| 3 | `docs/3_API_CONTRACTS.md` | Route reference, auth, rate limit, error handling |
| 4 | `docs/4_DEPLOYMENT.md` | Docker topology, runtime services, env vars |
| 5 | `docs/5_NAMING_CONVENTIONS.md` | Naming rules Python + TypeScript |
| 6 | `docs/6_KNOWN_ISSUES.json` | Post-mortems / known issues |
| 7 | `docs/7_CURRENT_SETTINGS.json` | Snapshot config/runtime hiện tại |

Task-specific reading:
- API → `docs/3_API_CONTRACTS.md`
- DB / schema → `docs/1_ARCHITECTURE.md` + `ops/init.sql`
- Deployment / Docker → `docs/4_DEPLOYMENT.md`
- Ingestion → `docs/2.1_WORKFLOWS_INGESTION.md`

---

## Must-Know

### 1. Hard-Delete Order (Strict)
`registry.delete()` → vectors → sections → file → DB row → purge

**Sections phải xóa trước DB row** để giữ toàn vẹn dữ liệu.

### 2. API Gateway
Browser → `/api/bep/*` → Next.js Route Handler → `getToken()` → Bearer → backend

**Token backend không được lộ ra browser.**

### 3. CSR Architecture

```text
Route (HTTP only) → Service (business logic) → Repository (data access)
```

| Layer | Forbidden |
|-------|-----------|
| Route | direct DB query, business logic |
| Service | `session.query()`, HTTP errors trực tiếp |
| Repository | business logic, HTTP concerns |

### 4. Multi-Tenant Boundary
- `platform_admin` quản trị toàn hệ thống
- `tenant_admin` chỉ thao tác trong tenant của mình
- mọi dữ liệu tenant-scoped phải filter bằng `tenant_id`
- không reintroduce ownership cũ kiểu `user_id` làm boundary chính

### 5. Stateless Chat
- không có persisted chat history trong product flow
- transcript chỉ sống ở frontend memory
- close chat = mất transcript
- backend nhận recent `messages` và tự inject instruction + RAG context

### 6. AI Provider Boundary
- Route không gọi SDK/model provider trực tiếp
- inference orchestration thuộc service layer
- LLM chính đi qua 9Router
- Embedding local mặc định đi qua Docker Model Runner
- Reranker ưu tiên NVIDIA NIM; local model chỉ là fallback

### 7. Async Rules
- I/O = `async def` + `await`
- CPU-bound = `await asyncio.to_thread()`
- Celery entrypoint mới dùng `asyncio.run()`

---

## Frontend / Webapp Rules

- Browser business requests phải đi qua `/api/bep/*`
- Không dùng `localStorage` để lưu transcript chat
- `sessionStorage` chỉ dùng cho state không nhạy cảm nếu thật sự cần
- UI phải tôn trọng role:
  - `platform_admin`
  - `tenant_admin`
- Nếu backend contract đổi, update cùng lúc:
  - `webapp/types/api.ts`
  - `webapp/lib/api-client.ts`
  - page/component liên quan

---

## Bug Fixing

**Không được hardcode để pass bug.**

Không bịa giá trị, không thêm bypass giả, không “fix cho qua”.
Phải truy tới root cause bằng:
- đọc log thật
- trace dependency thật
- verify output thật

Bug quan trọng cần ghi vào `docs/6_KNOWN_ISSUES.json` theo format:
- symptom
- root_cause
- resolution
- lesson_learned

---

## Code Quality

```bash
python -m black app --line-length=120
python -m flake8 app --select=F,E1,E2,E4,E9,W --ignore=E203,E501,W293,W292,W391,W503,W504
```

Exit code phải bằng `0`.

---

## Git Release Rules

### Khi nào cần tag release
- new feature
- breaking change
- major bug fix
- production deployment

### Tag format
`vMAJOR.MINOR.PATCH`

Ví dụ: `v0.2.0`

### Commit messages
Conventional Commits:
- `feat:`
- `fix:`
- `docs:`
- `perf:`
- `chore:`

---

## Line Endings

Tất cả source file phải dùng **LF (`\n`)**, không dùng CRLF.

Áp dụng cho:
- `*.py`
- `*.ts`, `*.tsx`, `*.js`, `*.jsx`
- `*.json`, `*.md`, `*.yml`, `*.yaml`
- `Dockerfile`, `*.sh`, `*.conf`

---

## Docker / Runtime Rules

### Build
```bash
cd chatbot-api
DOCKER_BUILDKIT=1 docker compose build
```

### Run
```bash
cd chatbot-api
docker compose up -d
```

### Current runtime shape
**Docker Backend (`chatbot-api/docker-compose.yml`)**
- `api` — FastAPI
- `workers` — Celery worker
- `qdrant` — Vector database
- `postgres` — Relational database
- `redis` — Cache & Message Broker
- `rustfs` — Object Storage
- `ai-proxy` — 9Router
- `traefik` — Reverse Proxy

**Standalone Frontend**
- `webapp` — Next.js (chạy độc lập ngoài Docker)

### Model runtime
- Embedding local mặc định: Docker Model Runner API
- Reranker mặc định: NVIDIA NIM
- Local reranker có thể tồn tại như fallback, không phải default happy path

---

## Documentation Sync (Mandatory)

Mọi thay đổi code phải cập nhật tài liệu tương ứng.

| Change | Update docs |
|--------|-------------|
| Thêm/xóa endpoint | `docs/3_API_CONTRACTS.md` |
| Thay đổi architecture | `docs/1_ARCHITECTURE.md` |
| Thay đổi workflow | `docs/2_WORKFLOWS.json` + file workflow con |
| Thay đổi env/config default | `docs/7_CURRENT_SETTINGS.json` + `.env.example` |
| Thay đổi deployment | `docs/4_DEPLOYMENT.md` |
| Bug quan trọng | `docs/6_KNOWN_ISSUES.json` |
| Thay đổi naming | `docs/5_NAMING_CONVENTIONS.md` |

Nếu không chắc phải update file nào, ít nhất phải sync `docs/7_CURRENT_SETTINGS.json`.

---

## MCP / Tooling Preference

- `playwright` — verify UI sau thay đổi frontend
- `next-devtools` — debug Next.js
- `shadcn` — lookup component / best practice khi chỉnh UI
- `sequential-thinking` — bug khó, refactor lớn, quyết định kiến trúc

---

**Last Updated**: 2026-07-03
