## Summary

Describe what changed and why.

## Docs-First Compliance (Required)

- [ ] I read docs first before coding, in this order:
  - [ ] `AGENTS.md`
  - [ ] `docs/0_QUICK_REFERENCE.json`
  - [ ] `docs/1_ARCHITECTURE.md`
  - [ ] `docs/2_WORKFLOWS.json` + child docs (2.1-2.5)
  - [ ] `docs/3_API_CONTRACTS.md`
  - [ ] `docs/4_DEPLOYMENT.md`
  - [ ] `docs/2.1_WORKFLOWS_INGESTION.md` (if ingestion/retrieval related)
- [ ] I can answer all 12 preflight checks from AGENTS.md

## Docs/Memory Update (Required for code changes)

- [ ] This PR updates at least one docs/memory source when code/behavior changes.
- [ ] If conflict, `docs/` is treated as source of truth.

## Validation

- [ ] I ran relevant checks for changed areas.
- [ ] I reviewed API/contract impact (if any) and updated frontend/contracts accordingly.
- [ ] HTTPException status codes follow policy (`status.HTTP_*`, no raw numeric literals).
