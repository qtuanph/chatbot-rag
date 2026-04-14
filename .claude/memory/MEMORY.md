# Memory Index

Persistent memory for chatbot-rag project. Optimized for AI context quality.

## Active Memory Files

### User Context
- **[user_profile.md](user_profile.md)** (5.6KB)
  - User role: Senior developer/architect
  - Preferences: Detail-oriented, architecture-first, Vietnamese
  - Working style: Docker-first, local-first, hierarchical indexing
  - Communication: Direct, technical, detailed explanations

### Critical Lessons
- **[database_credentials_structure.md](database_credentials_structure.md)** (2.2KB)
  - PostgreSQL admin vs app user passwords
  - Volume recreation requirements
  - Authentication troubleshooting

### Project Architecture
- **[architecture_summary.md](architecture_summary.md)** (7KB)
  - Technology stack (local embedding BAAI/bge-m3, rule-based refiner)
  - Key decisions and invariants
  - Configuration rules (.env, not .env.example)
  - Common pitfalls and solutions

### Rules & Updates
- **[rules_and_updates.md](rules_and_updates.md)** (4.2KB)
  - **CRITICAL**: Memory update rule (MANDATORY when changes occur)
  - Recent updates: Chat LLM model, API key cleanup, frontend migration
  - Upcoming: RAG v2 (multimodal + 2-stage retrieval)
  - Implementation plan reference

## Memory Stats

- **Total files:** 4 (down from 9)
- **Total size:** ~19KB (down from 48KB)
- **Redundancy:** 0% (all duplicates removed)

## Key Context for AI Agents

### Project Identity
- **What:** Docker-first hierarchical RAG chatbot for Vietnamese documents
- **Target:** On-premise deployment (customer infrastructure)
- **Architecture:** Hierarchical indexing (NOT flat chunking)
- **Status:** 85% complete, production hardening phase

### Critical Architecture Points
1. **Embedding**: BAAI/bge-m3 LOCAL (not Google Gemini Embedding)
2. **Refiner**: Rule-based (0GB VRAM, not Qwen AI model)
3. **Chat LLM**: Gemini external (temporary, will migrate to local vLLM)
4. **Ingestion**: Docling + EasyOCR → LlamaIndex hierarchy
5. **Retrieval**: Hierarchical tree structure preserved

### Configuration Rule
🔒 **STRICT:** All changes in `.env`, NEVER in `.env.example`

### Common Mistakes to Avoid
1. Don't call provider SDKs directly (use adapters)
2. Don't use flat chunking (preserve hierarchy)
3. Don't edit .env.example (edit .env instead)
4. Don't change database password without recreating volume
5. Don't skip Docker rebuild after code changes

## Maintenance

**Review schedule:** After major milestones
**Archive when:** Features completed, tasks resolved
**Delete when:** Outdated, duplicate, temporary notes

## Last Updated
- 2026-04-14: **CRITICAL UPDATE** - Added memory update rule and recent changes
  - Created: rules_and_updates.md (MANDATORY memory update rule)
  - Updated: architecture_summary.md (RAG v2 info)
  - Recent changes: gemma-4-26b-a4b-it model, API key cleanup, Nuxt.js frontend
  - Upcoming: RAG v2 (multimodal + 2-stage retrieval)
- 2026-04-13: **MAJOR CLEANUP** - Reduced from 9 files (48KB) to 3 files (15KB)
  - Removed: implementation_gaps.md, project_cleanup_2026_04_13.md, README.md
  - Removed: external_resources.md, project_context.md, architecture_clarifications.md
  - Created: architecture_summary.md (condensed)
  - Kept: user_profile.md, database_credentials_structure.md
