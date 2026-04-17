# Memory Index

Persistent memory for chatbot-rag project.

## Active Memory Files

### User Context
- **[user_profile.md](user_profile.md)** — Developer preferences and working style

### Critical Lessons
- **[database_credentials_structure.md](database_credentials_structure.md)** — PostgreSQL admin vs app user passwords

### Project Architecture
- **[architecture_summary.md](architecture_summary.md)** — 2-stage retrieval, key decisions

## Key Context

- **What:** Docker-first hierarchical RAG chatbot for Vietnamese documents
- **Architecture:** 2-stage retrieval (Sections → Chunks) with PostgreSQL + Qdrant
- **Frontend:** Next.js 16 (active in `webapp/`)
- **Status:** Production hardening phase

## Last Updated
- 2026-04-17: Synced frontend context and current project state
