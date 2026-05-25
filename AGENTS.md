# Agent Guardrails

## Docs First (MANDATORY - Read in Order)

| Priority | File | Purpose |
|----------|------|---------|
| 0 | `docs/0_QUICK_REFERENCE.json` | Cheat sheet — rules, env vars, data map, anti-patterns |
| 1 | `docs/1_ARCHITECTURE.md` | Tech stack, data model, storage, CSR, hard-delete order, AI control |
| 2 | `docs/2_WORKFLOWS.json` | Workflow index (children: 2.1-2.5) |
| 2.1 | `docs/2.1_WORKFLOWS_INGESTION.md` | Document ingestion pipeline |
| 2.2 | `docs/2.2_WORKFLOWS_CHAT.md` | Chat retrieval generation |
| 2.3 | `docs/2.3_WORKFLOWS_DELETE.md` | Hard delete workflow |
| 2.4 | `docs/2.4_WORKFLOWS_AUDIT.md` | Audit logging |
| 2.5 | `docs/2.5_WORKFLOWS_ANALYTICS.md` | Analytics data flow |
| 3 | `docs/3_API_CONTRACTS.md` | Route reference, security, rate limits, error handling |
| 4 | `docs/4_DEPLOYMENT.md` | Docker topology, Traefik v3.7, env vars, health probes, Celery config |
| 5 | `docs/5_NAMING_CONVENTIONS.md` | Python/TS naming standards, dict keys, async rules |
| 6 | `docs/6_KNOWN_ISSUES.json` | Bug tracking, post-mortems |
| 7 | `docs/7_CURRENT_SETTINGS.json` | Current settings — all defaults, env vars, runtime parameters |

Task-specific additional reading: API→3, DB→1+init.sql, Deployment→4, Ingestion→2.1

---

## Must-Know (No Excuses)

### 1. Hard-Delete Order (STRICT)
`registry.delete()` → vectors → sections → file → DB row → purge
**Sections BEFORE DB row** — referential integrity.

### 2. 5-Stage Retrieval
Hybrid search (dense+BM25 RRF) → section grouping (≥0.25) → dedup → rerank → **Neighbor Expansion (Soi sáng)** → full section context to LLM.

### 3. API Gateway
Browser → `/api/bep/` → Next.js Route Handler → `getToken()` → Bearer → backend. **Token never exposed to browser.**

### 4. Hardware Auto-Detect
`app/core/hardware.py` — 3-tier VRAM-aware scaling. **TEI containers (ai-embedding, ai-reranker) are the only GPU services.**

### 5. Provider Boundary
Routes NEVER call AI provider SDK directly. `ChatService` owns orchestration. Proxy bridge: `AIProxyBridge` in `app/adapters/ai/proxy_bridge.py`. Provider config managed via 9Router Dashboard (port 2908), not via FastAPI admin endpoints.

### 6. Async Rules
- All I/O (DB, Redis, Qdrant, S3) = `async def` + `await`
- CPU-bound (OCR, Embed) = `await asyncio.to_thread()`
- Celery → `asyncio.run()` at entry point only

---

## CSR Architecture (Mandatory)

```
Route (HTTP only) → Service (business logic) → Repository (data access)
```

| Layer | Forbidden |
|-------|-----------|
| Route | `SessionLocal`, business logic, direct DB queries |
| Service | `session.query()`, `http_errors.*` — raise `ValueError`/`RuntimeError` only |
| Repository | Business logic, HTTP concerns — return dicts, not ORM models |

### Module Map
`auth` · `documents` · `chat` · `analytics` · `system`

---

## Bug Fixing (MANDATORY)

**CRITICAL RULE: KHÔNG ĐƯỢC BỊA GIÁ TRỊ ĐỂ PASS BUG.**
Do not make up variables, hardcode bypasses, or hallucinate fixes just to suppress errors. You MUST fix bugs according to the principles and reality of the project (investigate root causes, check real script outputs, and trace dependencies). This avoids fixing the same bug over and over again.

Post-mortem in `docs/6_KNOWN_ISSUES.json` — Symptom → Root Cause → Resolution → Lesson Learned.

---

## Code Quality (Pre-Commit)

```bash
python -m black app --line-length=120
python -m flake8 app --select=F,E1,E2,E4,E9,W --ignore=E203,E501,W293,W292,W391,W503,W504
# Exit code MUST be 0
```

---

## Git Release Rules

### Tag + Release when:
- New feature, breaking change, major bug fix, production deployment
- Trivial commits (typo, comment fix, reformat, WIP, docs-only): **no tag needed**

### Tag format: `vMAJOR.MINOR.PATCH` (e.g., `v1.2.0`)

### Commit messages: Conventional Commits
`feat:` · `fix:` · `chore:` · `docs:` · `perf:`

---

## Line Endings (CRITICAL for Docker Build)

**All source files MUST use LF (`\n`) line endings, NOT CRLF (`\r\n`).**

Windows tools may create CRLF, which causes Docker containers to fail with errors like:
```
set: -e: invalid option
'\r': command not found
```

### Rules

| File type | Must use |
|-----------|----------|
| `*.py`, `*.sh`, `*.conf`, `*.yaml`, `*.yml`, `*.json`, `*.md`, `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `Dockerfile` | **LF only** |

### How to Fix on Windows

```powershell
# Option 1: git renormalize (fixes all tracked files)
git add --renormalize .
git commit -m "fix: normalize line endings to LF"
```

### CI Guardrail

`.github/workflows/line-ending-guardrail.yml` automatically checks all PRs for CRLF and fails the build if found.

### Prevention

Add to `.gitattributes` (already present):
```
* text=auto
*.sh      eol=lf
*.py      eol=lf
*.conf    eol=lf
...
```

---

## MCP Servers

| Server | Purpose |
|--------|---------|
| `playwright` | Browser testing for UI changes |
| `sequential-thinking` | Deep reasoning for bugs, refactoring, new features |
| `next-devtools` | Next.js debugging and inspection |
| `shadcn` | UI component lookup for shadcn/ui |

**When to use:**
- `playwright` — any UI/code change → verify in browser
- `sequential-thinking` — bug fixes, refactoring, new features → think through before coding
- `next-devtools` — Next.js specific debugging
- `shadcn` — when adding UI components

---

## Docker Build Rules (HuggingFace Cache)

**Nguyên tắc:** Build nhanh, model chỉ tải ở runtime.

### Build & Run Commands

```bash
# Build image (fast, cache-aware)
DOCKER_BUILDKIT=1 docker compose build

# Start full stack (lần đầu: download model vào hf-cache volume)
docker compose up -d

# Stop stack (volume giữ nguyên)
docker compose down

# Restart (dùng cache, không re-download)
docker compose restart
```

### Runtime Model Init

- Model download xảy ra ở **runtime** (TEI containers), không phải build
- Cache nằm trong `hf-cache` volume — shared giữa ai-embedding, ai-reranker
- Restart container dùng lại cache, không re-download
- Lần đầu start có thể mất 3-5 phút tải model

### Security

- `HF_TOKEN` không trong Dockerfile ARG/build-arg
- Token runtime từ `.env` file
- Không `--build-arg HF_TOKEN`

### Debug Cache

```bash
# Xem cache trong container
docker exec api ls /home/qtuanph/.cache/huggingface

# Force re-download (xóa cache)
docker volume rm chatbot-rag_hf-cache
docker compose up -d
```

### Build Cache

| Layer | Cache | Notes |
|-------|-------|-------|
| System deps | BuildKit apt cache | Reuse nếu apt line không đổi |
| Python deps | BuildKit pip cache | Reuse nếu requirements.txt không đổi |
| App code | COPY layer | Chỉ invalidate khi code đổi |
| **Model** | **hf-cache volume** | **Runtime, không trong image** |

### Entrypoints

| Service | Entrypoint | Model |
|---------|-----------|-------|
| api | `ops/entrypoint-api.sh` | Embedding |
| workers | `ops/entrypoint-worker.sh` | Embedding |
| ai-embedding | TEI default CMD | gte-multilingual-base |
| ai-reranker | TEI default CMD | gte-multilingual-reranker-base |
| ai-proxy | (9Router default CMD) | 9Router tự start qua image entrypoint — không cần shell script |

---

## Documentation Sync (MANDATORY)

**Mọi thay đổi code PHẢI cập nhật tài liệu tương ứng.** Không được merge code mà không update docs.

| Thay đổi | Update docs nào |
|----------|----------------|
| Thêm/xóa endpoint | `docs/3_API_CONTRACTS.md` |
| Thay đổi architecture | `docs/1_ARCHITECTURE.md` |
| Thêm/xóa workflow | `docs/2_WORKFLOWS.json` + child |
| Thay đổi env var / config default | `docs/7_CURRENT_SETTINGS.json` + `.env.example` |
| Thay đổi deployment | `docs/4_DEPLOYMENT.md` |
| Fix bug quan trọng | `docs/6_KNOWN_ISSUES.json` (post-mortem) |
| Thay đổi naming convention | `docs/5_NAMING_CONVENTIONS.md` |

**Rule**: Nếu không chắc docs nào cần update, update `docs/7_CURRENT_SETTINGS.json` — đây là file snapshot config hiện tại mà AI đọc đầu tiên.

---

**Last Updated**: 2026-05-22