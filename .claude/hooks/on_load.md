# On Load Hook - Docs-First Checklist

**Choose your path based on task complexity. Primary source: `docs/` folder.**

## Path A: Quick Fix ⚡ (2 min)
1. Read: `docs/00_QUICK_REFERENCE.md` (cheat sheet)
2. Code: Make your small change
3. Update: Affected docs immediately after

## Path B: New Feature 📚 (5-10 min)
1. Read: `docs/00_QUICK_REFERENCE.md` (full)
2. Read: Task-specific doc in `docs/` folder:
   - Retrieval: `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
   - API: `docs/04_API_CONTRACT_AND_SECURITY.md`
   - Database: `docs/02_DATABASE_AND_PROJECT.md`
   - Deployment: `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md`
3. Code: Implement with confidence
4. Update: Affected docs immediately after

## Path C: Deep Dive 🔍 (15+ min)
1. Read: `docs/00_QUICK_REFERENCE.md`
2. Read: `docs/01_SYSTEM_ARCHITECTURE.md`
3. Read: `docs/03_CORE_WORKFLOWS.md`
4. Read: `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
5. Supplementary: Other docs in `docs/` as needed
6. Code: Implement major changes
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

**All rules & patterns**: See `docs/00_QUICK_REFERENCE.md`
**System design**: See `docs/01_SYSTEM_ARCHITECTURE.md`
**Everything**: See `docs/` folder


