---
name: project
description: Core architecture (condensed) — see docs/ for details
type: project
---

# Architecture Summary - chatbot-rag

**Single source of truth**: Start with `AGENTS.md`, then use `docs/` folder. This file is a quick reference only.

## 🎯 Core Stack (One-liner)
- FastAPI + Celery + PostgreSQL + Qdrant + BAAI/bge-m3 (local) + Google AI (chat)

## ✨ Key Features

| Feature | Status | Link |
|---------|--------|------|
| **Hierarchical indexing** (docs → sections → chunks) | ✅ | `docs/06_INGESTION_AND_RETRIEVAL_STRATEGY.md` |
| **2-stage retrieval** (coarse section → fine chunk) | ✅ | `docs/06_INGESTION_AND_RETRIEVAL_STRATEGY.md` |
| **Smart OCR** (2-pass: no-OCR for native PDFs) | ✅ | `docs/03_CORE_WORKFLOWS.md` |
| **PostgreSQL section store** | ✅ | `docs/02_DATABASE_AND_PROJECT.md` |
| **Canonical tree order** (`order_index` + page spans) | ✅ | `docs/02_DATABASE_AND_PROJECT.md` |
| **Qdrant vectors with section_id** | ✅ | `docs/02_DATABASE_AND_PROJECT.md` |
| **Shared file-format helper** | ✅ | `app/core/file_formats.py` |
| **Admin document detail table view** | ✅ | `webapp/app/(main)/admin/documents/[id]/page.tsx` |
| **Async ingestion + pipeline recovery** | ✅ | `docs/03_CORE_WORKFLOWS.md` |
| **Rule-based AI Refiner** (0GB VRAM) | ✅ | `docs/03_CORE_WORKFLOWS.md` |
| **Query embedding cache** (1h TTL) | ✅ | `docs/06_INGESTION_AND_RETRIEVAL_STRATEGY.md` |
| **Production hardening** (5 phases) | ✅ | See `CHANGELOG.md` in root |
| **Next.js 16 + SSE chat + admin dashboard** | ✅ | `README.md` |

## 🚀 Quick Commands

```bash
docker compose up --build          # Start all services
docker compose logs -f api         # View API logs
curl http://localhost:8000/api/v1/health  # Health check
```

## 📚 Documentation Map

| Topic | File |
|-------|------|
| **Rules & patterns cheat sheet** | `AGENTS.md` → `docs/00_QUICK_REFERENCE.json` |
| **System design** | `docs/01_SYSTEM_ARCHITECTURE.md` |
| **Database schema** | `docs/02_DATABASE_AND_PROJECT.md` |
| **Workflows** (ingestion, chat, retrieval) | `docs/03_CORE_WORKFLOWS.md` |
| **API contracts & security** | `docs/04_API_CONTRACT_AND_SECURITY.md` |
| **Deployment & monitoring** | `docs/05_DEPLOYMENT_AND_OBSERVABILITY.md` |
| **2-stage RAG deep dive** | `docs/06_INGESTION_AND_RETRIEVAL_STRATEGY.md` |
| **AI guidance** (detailed) | `AGENTS.md` |

## 🔑 Three Invariants (Never break these)

1. **Async Ingestion** — Upload returns `task_id`, parsing async via Celery
2. **2-Stage Retrieval** — Query → Stage 1 (sections, ≥0.30) → Stage 2 (chunks, ≥0.35)
3. **Hard-Delete Ordering** — registry → vectors → file → DB → purge

## Last Updated
- 2026-04-17: Simplified to reference docs/ folder only

- 2026-04-17: Synced production config guardrails and dev-only env template clarification
