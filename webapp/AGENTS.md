# Frontend Agent Rules

## This Frontend is Coupled to Backend RAG

This is NOT a standalone Next.js app. Read backend docs before making changes.

**MUST READ** (in order, ALL required):
1. `../AGENTS.md` (repo guardrails)
2. `../docs/0_QUICK_REFERENCE.json` (rules & patterns)
3. `../docs/1_ARCHITECTURE.md` (architecture, data model, AI control)
4. `../docs/3_API_CONTRACTS.md` (API contracts, security baseline)
5. `../docs/2_WORKFLOWS.json` (chat session lifecycle, workflows - children: 2.1-2.5)
6. `../docs/5_NAMING_CONVENTIONS.md` (variable, function, file naming)

## Critical Coupling Points

### Chat Streaming Contract (MUST NOT break)
- Backend returns 2-stage retrieval citations: section_id + chunk_id + score
- Frontend displays: "Source: [filename] - Section: [heading]"
- Chunk not found → fallback to section-only citation
- SSE final event includes `stats`: total_ms, ttft_ms, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd
- Stats bar displays: time, TTFT, chars, token count, estimated cost ($X.XXXX)
- AbortController: stream cancelled on unmount or new message submission

### Chat Session Lifecycle (MUST understand)
- **Default**: Empty "Chat mới" on page load (no session restore)
- **Sidebar**: `ChatView` wraps `ChatSidebar` + `ChatPanel` with nested `SidebarProvider`
- **New session**: `POST /chat/sessions` creates empty session → sidebar updates
- **Switch session**: Click in sidebar → ChatPanel loads messages via controlled `sessionId` prop
- **Auto-title**: Backend sets title from first query (80 chars) → `onSessionUpdate` updates sidebar
- **Cleanup**: Sessions hard-deleted after 30 days by Celery Beat (no soft-delete)
- **Ordering**: `GET /chat/sessions` returns `updated_at DESC` (recently active first)
- **Files**: `chat-view.tsx` (orchestrator), `chat-sidebar.tsx` (session list), `chat-panel.tsx` (controlled panel)

### API Gateway Proxy (MUST respect)
- Browser calls `/api/bep/v1/...` only — NEVER sends Bearer token
- Route Handler reads JWT from HttpOnly cookie via `getToken()` → attaches Bearer header
- SSE streamed as `ReadableStream`
- File upload: `multipart/form-data` with `duplex: 'half'`

### Admin Dashboard (MUST match backend)
- Upload status: PROCESSING / COMPLETED / ERROR
- DO NOT change statuses without updating backend Celery task states
- Admin analytics page: `/admin/analytics` — KPI cards, daily token chart, cost comparison table
- Analytics API: `GET /analytics/stats` — admin sees system-wide, member sees own sessions

### Member Stats
- Welcome screen in ChatPanel shows per-user stats: messages, tokens, cost
- Uses `analyticsApi.getStats()` — scoped to user's own sessions

### Auth Token Refresh (MUST respect backend)
- JWT tokens (PyJWT) with 1-hour expiry, role cached in payload
- Blacklist singleton on backend — token checked via Redis
- Logout must call `POST /api/v1/auth/logout`

## Frontend Stack

- **Next.js 16** — check `package.json` for exact version
- **next-auth v5** with custom JWT provider
- **Tailwind CSS** + **shadcn/ui v4** (uses @base-ui/react, NOT Radix)
- **API**: Tight coupling to `../docs/3_API_CONTRACTS.md` endpoints

## Common Changes

### Adding new API endpoint to chat
1. Backend dev adds endpoint → updates `docs/3_API_CONTRACTS.md`
2. Wait for docs update before implementing frontend
3. Update `lib/api-client.ts` to call new endpoint
4. Test via Postman first

### Changing auth flow
1. Read `../docs/3_API_CONTRACTS.md` → Auth section
2. Update backend first
3. Update `lib/auth.ts` to match
4. Verify against tests

---

**Bottom Line**: Backend architecture is in `../docs/`. Frontend adapts to backend contracts.
