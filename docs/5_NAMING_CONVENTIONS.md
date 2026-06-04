# Naming Conventions

Nguồn chuẩn cho cách đặt tên trong backend Python và frontend TypeScript.

## Python Backend

### Quy tắc chung

| Nhóm | Quy tắc | Ví dụ |
|------|--------|-------|
| Function / method | `snake_case` | `get_tenant_usage_summary`, `hash_password` |
| Class | `PascalCase` | `TenantService`, `PublicInferenceService` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_TASKS_PER_CHILD` |
| Variable | `snake_case` | `tenant_id`, `document_id`, `query_text` |
| Private helper | `_leading_underscore` | `_build_messages` |
| Boolean | `is_`, `has_`, `can_`, `should_` | `is_platform_admin`, `has_access` |
| Optional type | `X | None` | `str | None` |
| Generic built-in | `dict`, `list`, `tuple` | `dict[str, Any]` |

### Database

| Thành phần | Quy tắc | Ví dụ |
|-----------|--------|-------|
| Tên bảng | `snake_case` | `tenant_api_keys`, `document_sections` |
| Tên cột | `snake_case` | `tenant_id`, `created_at`, `cost_micros_vnd` |
| Thời gian | hậu tố `_at` | `created_at`, `updated_at` |
| Ngày | hậu tố `_date` | `start_date` |
| Khóa ngoại | `{entity}_id` | `tenant_id`, `user_id`, `document_id` |
| Metadata dict key | `snake_case` | `artifact_metadata`, `section_id` |

### Service / Repository

| Thành phần | Quy tắc | Ví dụ |
|-----------|--------|-------|
| Repository | `{Entity}Repository` | `DocumentRepository`, `AnalyticsRepository` |
| Service | `{Domain}Service` | `AuthService`, `TenantService` |
| DI factory | `get_{name}` | `get_auth_service`, `get_tenant_service` |
| Utility function | `verb_noun` | `compute_cost_micros_vnd`, `to_vietnam_iso` |

### Boundary theo ID

| Ngữ cảnh | Quy tắc | Ví dụ |
|---------|--------|-------|
| Public API | dùng tên đầy đủ | `tenant_id`, `document_id`, `user_id` |
| Worker payload | chỉ truyền primitive / id / uri | `tenant_id`, `document_id`, `file_path` |
| Internal locals | được rút ngắn nếu rõ nghĩa | `doc_ids` trong scope hẹp |

## React / TypeScript Frontend

| Nhóm | Quy tắc | Ví dụ |
|------|--------|-------|
| Component | `PascalCase` | `TenantSettingsForm`, `ChatMessage` |
| Hook | `use` prefix | `useSession`, `useMemo` |
| Event handler | `handle` / `on` prefix | `handleSave`, `onSelectedTenantIdChange` |
| Boolean | `is` / `has` / `can` / `should` | `isLoading`, `canUpload` |
| Variable | `camelCase` | `selectedTenantId`, `rawApiKey` |
| Constant | `UPPER_SNAKE_CASE` | `DATE_RANGES` |
| Props interface/type | `PascalCase` + `Props` | `DocumentCatalogProps` |

### Tên file

| Loại | Quy tắc | Ví dụ |
|------|--------|-------|
| Component | `kebab-case.tsx` | `chat-message.tsx`, `tenant-select.tsx` |
| Utility | `kebab-case.ts` | `api-client.ts`, `format.ts` |
| Route | chuẩn Next.js | `page.tsx`, `layout.tsx`, `route.ts` |

## Chuẩn async

| Quy tắc | Bắt buộc |
|--------|---------|
| I/O | `async def` + `await` |
| CPU-bound | `asyncio.to_thread()` hoặc executor |
| DB session | `AsyncSession` / `AsyncSessionLocal` |
| Không blocking | không dùng `time.sleep()` hoặc `requests` trong async path |

## Quy ước đặc biệt của project

1. Không thêm mới persisted chat session naming cho product flow stateless.
2. Tenant là business boundary chính:
   - ưu tiên `tenant_id`
   - không đưa ownership chính quay lại `user_id`
3. Tiền tệ luôn theo chuẩn:
   - `cost_micros_vnd`
   - `currency_code`
4. Helper dùng chung toàn project đặt ở `app/utils/`.
5. Helper chỉ dùng nội bộ module đặt trong chính module đó.
6. Không đổi tên tùy hứng giữa các layer cho cùng một khái niệm.
