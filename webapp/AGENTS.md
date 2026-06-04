# Frontend Agent Rules

## Inherit Parent Project Rules First

Frontend work in this folder must follow the root project guardrails in:
- `../AGENTS.md`
- `../docs/0_QUICK_REFERENCE.json`
- `../docs/1_ARCHITECTURE.md`
- `../docs/3_API_CONTRACTS.md`
- `../docs/5_NAMING_CONVENTIONS.md`

If this file and the parent project guidance differ, follow the parent project guidance and the current backend code.

## Current Frontend Target

This webapp is no longer built around persisted chat sessions.

Current product direction:
- multi-tenant SaaS
- `platform_admin` manages the platform
- `tenant_admin` operates only inside their tenant
- chat is stateless
- transcript lives in frontend memory only
- tenant settings and instruction are tenant-scoped
- public integration is OpenAI-compatible, but internal webapp chat goes through backend-authenticated internal routes

## Frontend Expectations

- Do not restore legacy chat session sidebar behavior
- Do not use `localStorage` for transcript persistence
- Do not expose backend Bearer token to browser code
- Keep browser calls routed through `webapp/app/api/bep/[...path]/route.ts`
- Respect backend role names exactly:
  - `platform_admin`
  - `tenant_admin`
- Respect tenant boundaries in UI state and API calls

## UI Scope

The webapp should provide:
- `platform_admin`
  - tenant management
  - tenant API key management
  - tenant document management
  - tenant usage visibility
  - tenant chat testing
- `tenant_admin`
  - tenant chat testing
  - tenant document read-only view
  - tenant usage view
  - tenant instruction editing

## Implementation Guidance

- Prefer shared utilities in `lib/` and reusable UI in `components/`
- If a module needs internal-only helpers, keep them inside that module scope
- Remove or replace legacy session-centric code instead of keeping dead flows around
- When backend contracts change, update `types/api.ts`, `lib/api-client.ts`, and affected pages together
