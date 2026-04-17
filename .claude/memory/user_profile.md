---
name: user
description: User profile and preferences for chatbot-rag project
type: user
---

# User Profile - chatbot-rag Project

## Basic Information
- **Project Role**: Lead Developer / Architect
- **Experience Level**: Senior
- **Primary Language**: Vietnamese
- **Working Style**: Detail-oriented, architecture-first

## Technical Background
- Strong knowledge of FastAPI, Docker, RAG systems, Qdrant, LLM integration, hierarchical document indexing, Vietnamese NLP

## Communication Preferences
- **Language**: Vietnamese for explanations, English for code
- **Style**: Direct, technical, detailed
- **Likes**: Detailed explanations with reasoning, architecture diagrams, understanding "why"
- **Dislikes**: Generic advice, skipping details, "just trust me"

## Development Environment
- **OS**: Windows 11
- **Shell**: PowerShell
- **Docker**: Installed and running
- **GPU**: NVIDIA (for local models)

## Architecture Philosophy
- Docker-first, self-hosted, on-premise focus
- Vietnamese enterprise documents, hierarchical indexing (NOT flat chunking)

## Technology Choices
- **Embedding**: BAAI/bge-m3 LOCAL (offline)
- **Refiner**: Rule-based (0GB VRAM)
- **Chat LLM**: Google AI gemma-4-26b-a4b-it (temporary, will migrate to vLLM)
- **Frontend**: Next.js (new, replacing Nuxt.js)
- **Storage**: RustFS (S3-compatible), PostgreSQL + Qdrant + Redis

## Working Style
- Modify existing files directly, no v1/v2 separation during dev
- Prefer in-place overwrite for documentation updates (single canonical doc set)
- Prefer incremental batches (small changes per batch, easy review/rollback)
- Docker reset (`docker volume rm`) is acceptable for schema changes
- Concise updates, no unnecessary backward compatibility in dev

## Last Updated
- 2026-04-17: Synced shell/tooling and implementation preferences
