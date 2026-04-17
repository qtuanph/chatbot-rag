---
name: project
description: Core architecture and key decisions for chatbot-rag (condensed)
type: project
---

# Architecture Summary - chatbot-rag

## 2-Stage Retrieval Architecture

- **Section extraction**: Markdown → split by headings → sections (Level 1, stored in PostgreSQL)
- **Chunk splitting**: Each section → chunks (Level 2, ~400 tokens, ~75 overlap, stored in Qdrant)
- **Retrieval**: Query → Stage 1 (coarse section search, top 3, threshold ≥ 0.30) → Stage 2 (fine chunk search, top 5, threshold ≥ 0.35) → fallback to flat retrieval

## Core Stack
- FastAPI + Celery + Redis + PostgreSQL + Qdrant + RustFS
- BAAI/bge-m3 local embedding (1024-dim, offline)
- Google AI gemma-4-26b-a4b-it (chat LLM)
- Rule-based refiner (0GB VRAM)
- EasyOCR (vi+en)

## Key Design Decisions
- **Sections in PostgreSQL**: Fast section-level lookup for Stage 1
- **Chunks in Qdrant**: Fine-grained vector search with section_id for Stage 2
- **Worker needs db_session**: IngestionPipeline accepts db_session for SectionRepository

## Implementation Status
- ✅ 2-stage retrieval, section storage, rule-based refiner, hard-delete, Tree API, Next.js frontend
- 🔜 Performance tuning for large documents, monitoring hardening
- ❌ Structured logging, backup automation

## Important Invariants

| Rule | Required Behavior |
|------|-------------------|
| Async ingestion | Upload must return immediately with task_id |
| 2-stage retrieval | Section search (coarse) → Chunk search (fine) |
| Hard-delete order | registry → vectors → sections → file → DB → purge |
| Score threshold | Sections ≥ 0.30, Chunks ≥ 0.35 |
| Route throttling | Sensitive auth routes include health/tree throttling with 429 on limit |
| Auth validation | Username normalized + bounded, role strict enum admin/member |
| Middleware fallback | Production enables coarse global rate-limit middleware as safety net |
| Error handling | Route-level HTTP errors are centralized via app/core/http_errors.py |
| CI guardrail | Status code policy also forbids direct raise HTTPException in API layer |
| Error envelope | Global exception handlers return unified JSON error payload with backward-compatible detail |
| Webapp runtime image | Uses Next standalone artifacts; avoids full builder node_modules copy |
| Production config | app/core/config.py blocks wildcard hosts, localhost CORS, relaxed rate limits, insecure S3 in production |
| Compose exposure | Published service ports are bound to 127.0.0.1 by default for local/dev safety |

## Last Updated
- 2026-04-17: Synced production config guardrails and dev-only env template clarification
