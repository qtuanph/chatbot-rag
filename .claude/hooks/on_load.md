# On Load Hook - Docs-First Checklist

**Choose your path based on task complexity. Primary source: `AGENTS.md` first, then `docs/` folder.**

## Path A: Quick Fix ⚡ (2 min)
1. Read: `AGENTS.md`
2. Read: `docs/00_QUICK_REFERENCE.json` (cheat sheet)
3. Code: Make your small change
4. Update: Affected docs immediately after

## Path B: New Feature 📚 (5-10 min)
1. Read: `AGENTS.md`
2. Read: `docs/00_QUICK_REFERENCE.json` (full)
3. Read: Task-specific doc in `docs/` folder:
   - Retrieval: `docs/06_INGESTION_AND_RETRIEVAL_STRATEGY.md`
   - API: `docs/04_API_CONTRACT_AND_SECURITY.md`
   - Database: `docs/02_DATABASE_AND_PROJECT.md`
   - Deployment: `docs/05_DEPLOYMENT_AND_OBSERVABILITY.md`
4. Code: Implement with confidence
5. Update: Affected docs immediately after

## Path C: Deep Dive 🔍 (15+ min)
1. Read: `AGENTS.md`
2. Read: `docs/00_QUICK_REFERENCE.json`
3. Read: `docs/01_SYSTEM_ARCHITECTURE.md`
4. Read: `docs/03_CORE_WORKFLOWS.md`
5. Read: `docs/06_INGESTION_AND_RETRIEVAL_STRATEGY.md`
6. Supplementary: Other docs in `docs/` as needed
7. Code: Implement major changes
8. Update: All affected docs

---

## Preflight Questions (Answer before coding)

1. **Retrieval strategy?** — 2-stage (Section search → Chunk search)
2. **Where are sections?** — PostgreSQL `document_sections` table
3. **Where are chunks?** — Qdrant vectors (with section_id metadata)
4. **Embedding model?** — BAAI/bge-m3 (1024-dim, local)
5. **Hard-delete order?** — registry → vectors → file → DB → purge

If unclear, re-read docs before coding.

---

**All rules & patterns**: See `AGENTS.md` first, then `docs/00_QUICK_REFERENCE.json`
**System design**: See `docs/01_SYSTEM_ARCHITECTURE.md`
**Everything**: See `docs/` folder


