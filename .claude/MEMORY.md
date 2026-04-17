# Memory Index

Project memory index for `.claude/memory/`.

## Read Order (Docs-First)

1. `../CLAUDE.md` (authoritative source)
2. `../docs/01_SYSTEM_ARCHITECTURE.md`
3. `../docs/03_CORE_WORKFLOWS.md`
4. `../docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
5. Then use memory files below as condensed context.

If any memory conflicts with `CLAUDE.md`, follow `CLAUDE.md` and update memory immediately.

## Active Memory Files

### User Context
- `memory/user_profile.md` - Developer preferences and working style

### Project Context
- `memory/architecture_summary.md` - Condensed architecture and invariants
- `memory/database_credentials_structure.md` - DB credential structure notes

### Memory Meta
- `memory/MEMORY.md` - Internal memory index for subfolder

## Update Protocol

Update memory files when there are changes in:
- Architecture or retrieval strategy
- API contracts or route behavior
- Database schema (`ops/init.sql`)
- Provider/model settings

Every update should include:
- What changed
- Why it changed
- Last updated date

## Last Updated
- 2026-04-17: Synced index with actual memory files and Docs-First policy
