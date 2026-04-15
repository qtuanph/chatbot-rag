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
- Google AI gemma-4-26b-a4b-it (chat LLM, temporary)
- Rule-based refiner (0GB VRAM)
- EasyOCR (vi+en)

## Key Design Decisions
- **Inline modifications**: No new files during dev, modify existing ones
- **Sections in PostgreSQL**: Fast section-level lookup for Stage 1
- **Chunks in Qdrant**: Fine-grained vector search with section_id for Stage 2
- **Worker needs db_session**: IngestionPipeline accepts db_session for SectionRepository

## Implementation Status
- ✅ 2-stage retrieval, section storage, rule-based refiner, hard-delete, Tree API
- 🔜 Next.js frontend (new), multimodal ingestion, monitoring
- ❌ Structured logging, backup automation

## Important Invariants

| Rule | Required Behavior |
|------|-------------------|
| Async ingestion | Upload must return immediately with task_id |
| 2-stage retrieval | Section search (coarse) → Chunk search (fine) |
| Hard-delete order | registry → vectors → sections → file → DB → purge |
| Score threshold | Sections ≥ 0.30, Chunks ≥ 0.35 |

## Last Updated
- 2026-04-15: Removed webapp/Nuxt references, frontend will be Next.js
