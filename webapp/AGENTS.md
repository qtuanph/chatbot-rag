# Frontend Agent Rules

## ⚠️ This Frontend is Coupled to Backend RAG

This is not a standalone Next.js app. Before making changes, understand the backend architecture.

**MUST READ** (in order):
1. `../CLAUDE.md` (backend mandatory rules)
2. `../docs/00_QUICK_REFERENCE.md` (rules & patterns)
3. `../docs/07_INGESTION_AND_RETRIEVAL_STRATEGY.md` (2-stage RAG)
4. `../docs/04_API_CONTRACT_AND_SECURITY.md` (API contracts this app uses)

## 🚨 Critical Coupling Points

### Chat Streaming Contract (MUST NOT break)
- Backend returns **2-stage retrieval citations**: section_id + chunk_id + score
- Frontend must display in format: "Source: [filename] - Section: [heading]"
- If chunk not found, graceful fallback to section-only citation
- See: `../docs/04_API_CONTRACT_AND_SECURITY.md` → Chat endpoint

### Admin Dashboard (MUST match backend)
- Shows upload status (PROCESSING/COMPLETED/ERROR)
- Shows document ingestion pipeline state
- **DO NOT** change these statuses without updating backend Celery task states
- See: `../docs/03_CORE_WORKFLOWS.md` → Ingestion workflow

### Auth Token Refresh (MUST respect backend)
- Backend uses JWT tokens with 1-hour expiry
- Token blacklist checked on every request (Redis)
- Logout must call `DELETE /api/v1/auth/logout` to blacklist token
- See: `../docs/04_API_CONTRACT_AND_SECURITY.md` → Auth

## 📚 Frontend Entry Point: Next.js

- **This is Next.js 16** — check `package.json` for exact version
- **Authentication**: next-auth v5 with custom JWT provider
- **Styling**: Tailwind CSS + shadcn/ui v4
- **API**: Tight coupling to `../docs/04_API_CONTRACT_AND_SECURITY.md` endpoints

## 🔄 Common Changes

### Adding new API endpoint to chat
1. Backend dev adds endpoint to `../app/api/routes/chat.py`
2. **Update** `../docs/04_API_CONTRACT_AND_SECURITY.md` with new endpoint
3. **Wait** for docs update before implementing frontend
4. Update `lib/api-client.ts` to call new endpoint
5. Test via Postman first (check examples in docs)

### Changing auth flow
1. **Read** `../docs/04_API_CONTRACT_AND_SECURITY.md` → Auth section
2. Update backend first
3. Update `lib/auth.ts` to match new flow
4. Verify against tests in `../tests/test_phase4_route_coverage.py`

---

**Bottom Line**: Backend architecture is documented in `../docs/`. Frontend must adapt to backend contracts, not the other way around.
