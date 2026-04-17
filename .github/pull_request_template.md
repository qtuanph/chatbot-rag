## Summary

Describe what changed and why.

## Docs-First Compliance (Required)

- [ ] I read docs first before coding, in this order:
  - [ ] `CLAUDE.md`
  - [ ] `docs/01_SYSTEM_ARCHITECTURE.md`
  - [ ] `docs/03_CORE_WORKFLOWS.md`
  - [ ] `docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md`
- [ ] I can answer preflight checks:
  - [ ] Retrieval strategy in use
  - [ ] Where sections are stored
  - [ ] Where chunks are stored
  - [ ] Embedding model and dimension
  - [ ] Hard-delete order and rationale

## Docs/Memory Update (Required for code changes)

- [ ] This PR updates at least one docs/memory source when code/behavior changes.
- [ ] If there is a conflict, `CLAUDE.md` is treated as source of truth and memory files are synced.

## Agent-Agnostic Confirmation

- [ ] This PR follows the same guardrails regardless of implementation agent (Claude Code, GitHub Copilot, or other automation).

## Validation

- [ ] I ran relevant checks for changed areas.
- [ ] I reviewed API/contract impact (if any) and updated frontend/contracts accordingly.
