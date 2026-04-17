# CLAUDE.md - Mandatory Rules for Claude Code

**This is your entry point.** Before any code edit, follow these rules.

## 🚨 MANDATORY (Non-negotiable)

1. **MUST read `docs/00_QUICK_REFERENCE.md` first** (5 min cheat sheet)
2. **MUST answer these 5 questions before coding**:
   - What is the retrieval strategy?
   - Where are sections stored?
   - Where are chunks stored?
   - What embedding model and dimension?
   - What is the hard-delete order and why?
3. **MUST read task-specific doc in `docs/` folder**
4. **MUST update `docs/` immediately after changes** (source of truth)

## 📚 Default Read Order

### Path A: Quick Fix (2 min)
1. `docs/00_QUICK_REFERENCE.md`
2. Code change
3. Update docs

### Path B: New Feature (10 min)
1. `docs/00_QUICK_REFERENCE.md`
2. Relevant doc in `docs/`:
   - Retrieval: `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
   - API: `docs/04_API_CONTRACT_AND_SECURITY.md`
   - DB: `docs/02_DATABASE_AND_PROJECT.md`
   - Deployment: `docs/06_DEPLOYMENT_AND_OBSERVABILITY.md`
3. Code change
4. Update docs

### Path C: Deep Dive (15+ min)
1. `docs/00_QUICK_REFERENCE.md`
2. `docs/01_SYSTEM_ARCHITECTURE.md`
3. `docs/03_CORE_WORKFLOWS.md`
4. `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
5. Other docs as needed
6. Code change
7. Update all affected docs

## ✅ Verification Checklist (Before Coding)

- [ ] Can answer all 5 preflight questions?
- [ ] Read relevant `docs/` file?
- [ ] Understand the constraint/rule I'm changing?

If NO to any → **STOP and re-read docs first**.

## 🔄 After Implementation

**MUST update `docs/` folder**:
- Architecture changes → `docs/01_SYSTEM_ARCHITECTURE.md`
- Retrieval changes → `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
- API changes → `docs/04_API_CONTRACT_AND_SECURITY.md`
- Database changes → `docs/02_DATABASE_AND_PROJECT.md` + `ops/init.sql`
- Services changes → `docs/08_SERVICES_ARCHITECTURE.md`

## 📍 Source of Truth

**`docs/` folder is authoritative.**
If you see outdated info here, update both this file and the relevant `docs/` file immediately.

---

**Quick Commands**:
```bash
docker compose up --build           # Start all services
curl http://localhost:8000/api/v1/health  # Health check
docker compose logs -f api          # View API logs
```

See `docs/00_QUICK_REFERENCE.md` for everything else.
