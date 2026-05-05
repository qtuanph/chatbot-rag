# Naming Conventions

> **Source of truth** for all variable, function, class, and file naming.

## Python Backend

### General Rules (PEP 8)

| Category | Rule | Example |
|----------|------|---------|
| Functions/Methods | `snake_case` | `get_session`, `build_bm25_index` |
| Classes | `PascalCase` | `ChatService`, `DocumentRepository` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_TASKS_PER_CHILD`, `_ALL_MODULES` |
| Variables | `snake_case` | `session_id`, `query_text` |
| Private | `_leading_underscore` | `_get_client`, `_refine_nodes` |
| Boolean prefix | `is_`, `has_`, `can_`, `should_` | `is_admin`, `has_permission` |
| Type annotations | `X \| None` (Python 3.10+) | `str \| None`, `list[str]` |
| Built-in generics | `dict`, `list`, `tuple` (not `Dict`, `List`) | `dict[str, Any]`, `list[str]` |
| No shadowing builtins | Never use `filter`, `type`, `id`, `input`, `list` | Use `text_filter`, `node_type` |

### Database

| Element | Rule | Example |
|---------|------|---------|
| Table names | `singular snake_case` | `document_sections`, `chat_messages` |
| Columns | `snake_case` | `created_at`, `actor_user_id` |
| Datetime suffix | `_at` | `created_at`, `updated_at`, `status_updated_at` |
| Date suffix | `_date` | `start_date` (date only, no time) |
| Foreign keys | `{column}_id` | `user_id`, `document_id` |
| Audit context | `actor_user_id` | Intentional: distinguishes actor from subject |
| Dict keys (metadata) | `snake_case` | `artifact_metadata`, `section_id` |

### Service/Repository Pattern

| Element | Naming | Example |
|---------|--------|---------|
| Repository | `{Entity}Repository` | `DocumentRepository`, `ChatRepository` |
| Service | `{Domain}Service` | `ChatService`, `AuthService` |
| Utility functions | `verb_noun` | `hash_password`, `get_bm25_encoder` |
| DI factories | `get_{dependency}` | `get_auth_service()`, `get_chat_repo()` |

### ID-First Boundaries

| Boundary | Rule | Example |
|----------|------|---------|
| Public API fields | Use full names | `document_id`, `session_id`, `user_id` |
| Internal query locals | Short forms allowed only in tight query context | `doc_ids` inside retrieval repository code |
| Worker payloads | Pass IDs/URIs, not rich dicts or ORM-like objects | `document_id`, `task_id`, `file_path` |
| Section lookup | Pair document and section identity | `(document_id, section_id)` |

## React / TypeScript Frontend

| Category | Rule | Example |
|----------|------|---------|
| Components | `PascalCase` | `ChatPanel`, `ChatMessage` |
| Hooks | `use` prefix | `useChat`, `useAuth` |
| Event handlers | `handle` / `on` prefix | `handleSubmit`, `onSessionUpdate` |
| Booleans | `is` / `has` / `can` / `should` prefix | `isLoading`, `hasPermission` |
| Variables | `camelCase` | `sessionId`, `accessToken` |
| Constants | `UPPER_SNAKE_CASE` | `API_BASE_URL`, `PAGE_SIZE` |
| Props interfaces | `PascalCase` + `Props` suffix | `ChatPanelProps` |
| API functions | `camelCase` in `api-client.ts` | `getMessages()`, `createSession()` |

### File Naming

| Type | Rule | Example |
|------|------|---------|
| Components | `PascalCase.tsx` | `ChatPanel.tsx`, `ChatMessage.tsx` |
| Utilities | `kebab-case.ts` | `api-client.ts`, `text-refiner.ts` |
| Routes | `lowercase` | `route.ts`, `page.tsx` |
| Config | `kebab-case` | `next.config.ts`, `tailwind.config.ts` |

## Enforced Standards

1. **Python 3.10+ syntax**: Use `X | None` not `Optional[X]`. Use `dict[str, Any]` not `Dict[str, Any]`.
2. **No builtin shadowing**: `filter`, `type`, `id`, `input`, `list`, `dict`, `set`, `object`, `range`.
3. **Consistent dict keys**: Same concept → same key name across codebase (e.g., always `artifact_metadata`, never `extra_metadata`).
4. **Public API uses full names**: `document_ids` in public APIs, `doc_ids` only in internal query logic.
5. **Short forms acceptable in**: loop variables (`msg` in logger), local temp variables.

## Async/Await Standards

| Rule | Requirement |
|------|-------------|
| I/O Operations | MUST be `async def` (Database, Redis, Qdrant, HTTP calls). |
| CPU-Bound Tasks | MUST use `asyncio.to_thread()` or `loop.run_in_executor()`. |
| Sync Wrapping | Utility methods wrapping sync logic (e.g. disk I/O) should use `_async` suffix. |
| Avoid Blocking | NEVER use `time.sleep()`, `requests`, or sync `open()` in async routes/services. |
| Session Handling | ALWAYS use `AsyncSession` and `AsyncSessionLocal`. No `SessionLocal`. |

### 8. Dict Key Canonical Names

To ensure consistency across the application when passing dictionaries around (especially JSON/metadata fields), use the following standardized keys:

- **`artifact_metadata`**: Use this exact string for any dictionary key or API response field representing a document's extra/flexible metadata.
  - ❌ `extra_metadata`
  - ❌ `metadata`
  - ✅ `artifact_metadata`
- **`parse_error`**: Use for storing textual error tracebacks.
  - ❌ `error_msg`
  - ✅ `parse_error`
