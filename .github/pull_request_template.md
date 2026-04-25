## Summary

Describe what changed and why.

## Docs-First Compliance (Required)

- [ ] I read docs first before coding, in this order:
  - [ ] `AGENTS.md`
  - [ ] `docs/00_QUICK_REFERENCE.json`
  - [ ] `docs/01_ARCHITECTURE.md`
  - [ ] `docs/02_WORKFLOWS.md`
  - [ ] `docs/03_API_CONTRACTS.md`
  - [ ] `docs/04_DEPLOYMENT.md`
  - [ ] `docs/05_INGESTION_RETRIEVAL.md` (if ingestion/retrieval related)
- [ ] I can answer all 12 preflight checks from AGENTS.md

## Docs/Memory Update (Required for code changes)

- [ ] This PR updates at least one docs/memory source when code/behavior changes.
- [ ] If conflict, `docs/` is treated as source of truth.

## Validation

- [ ] I ran relevant checks for changed areas.
- [ ] I reviewed API/contract impact (if any) and updated frontend/contracts accordingly.
- [ ] HTTPException status codes follow policy (`status.HTTP_*`, no raw numeric literals).
