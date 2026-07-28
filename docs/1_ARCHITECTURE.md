# 1 — Architecture

Tài liệu này mô tả kiến trúc hiện tại của `chatbot-rag` sau đợt rebuild RAG theo hướng structure-aware, multi-tenant, stateless chat.

## Tổng quan

```mermaid
flowchart TB
    %% Definitions
    subgraph Client [Client Zone]
        User([Người dùng / Trình duyệt])
    end

    subgraph Gateway [API & Routing Zone]
        Traefik[Traefik v3.7\nReverse Proxy]
    end

    subgraph Core [Backend & Compute Zone]
        FastAPI[FastAPI Backend\nCSR, JWT, RBAC]
        Workers[Celery Workers\nIngestion / Async]
    end

    subgraph AI [AI Proxy & Models Zone]
        Router[9Router\nLLM Proxy]
        ModelRunner[Docker Model Runner\nLocal Embeddings]
        NIM[NVIDIA NIM\nReranker]
        Parser[LlamaParse Cloud\n/ Docling Local OCR]
    end

    subgraph Data [Data & Storage Zone]
        Postgres[(PostgreSQL\nTenant, Auth, Feedback)]
        Qdrant[(Qdrant Vector DB\nSections & Chunks)]
        Redis[(Redis\nCache, Rate Limit, Queue)]
        RustFS[(RustFS\nFile Storage)]
        SQLite[(SQLite\nProvider Settings)]
    end

    %% Client -> Gateway
    User -->|HTTP/HTTPS| Traefik
    Traefik -->|Host('api.qtuanph.dev')| FastAPI

    %% Gateway -> Core

    %% Core -> Data
    FastAPI -->|Query / CRUD| Postgres
    FastAPI -->|Search / Filter| Qdrant
    FastAPI -->|Pub/Sub & Limit| Redis
    FastAPI -->|File Access| RustFS
    FastAPI -->|Load Config| SQLite
    
    Workers -->|Parse & Ingest| Postgres
    Workers -->|Index & Chunk| Qdrant
    Workers -->|Task Queue| Redis
    Workers -->|File Access| RustFS

    %% Core -> AI
    FastAPI -->|Chat / Inference| Router
    FastAPI & Workers -->|Embeddings| ModelRunner
    FastAPI -->|Reranking| NIM
    Workers -->|OCR & Markdown| Parser

    %% Styling
    classDef client fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px;
    classDef gateway fill:#f5f5f5,stroke:#666666,stroke-width:2px;
    classDef core fill:#e1d5e7,stroke:#9673a6,stroke-width:2px;
    classDef ai fill:#fff2cc,stroke:#d6b656,stroke-width:2px;
    classDef data fill:#d5e8d4,stroke:#82b366,stroke-width:2px;

    class User client;
    class Traefik gateway;
    class FastAPI,Workers core;
    class Router,ModelRunner,NIM,Parser ai;
    class Postgres,Qdrant,Redis,RustFS,SQLite data;
```

## Domain chính

- `platform_admin` quản trị toàn hệ thống
- `tenant_admin` chỉ thao tác trong tenant của mình
- mọi dữ liệu tenant-scoped phải luôn đi cùng `tenant_id`

### Shared Knowledge Base model (ADR-02 & v2.1)

- Entity `KnowledgeBase` với trạng thái lifecycle (Draft -> Published -> Deprecated).
- Document thuộc về KB (`documents.knowledge_base_id`).
- Phân quyền Tenant truy cập KB qua bảng `tenant_knowledge_bases` và `tenant_document_access`.
- Vector embeddings trong Qdrant được lưu duy nhất 1 lần cho mỗi document/section; retrieval pipeline sử dụng Qdrant payload filter theo danh sách tài liệu thuộc KB đã `published` mà Tenant được cấp quyền.

### Chat model (User Stateless / Admin Audit Persistence)

Chat từ góc nhìn Client/Người dùng là **stateless**:
- Transcript người dùng chỉ lưu ở memory tab frontend, không thể query lại qua API người dùng.
- Client gửi 6 tin nhắn gần nhất qua API request payload.

Từ góc nhìn Admin/System:
- Mỗi lượt hội thoại (turn) được tự động lưu **bất đồng bộ (fire-and-forget)** qua Celery task `save_conversation_turn_task` vào PostgreSQL (`conversations` & `conversation_messages`).
- Phục vụ mục đích thu thập thông tin, audit, QA, tính toán chi phí, và escalation cho Admin.
- Thời gian lưu trữ cấu hình qua `CHAT_RETENTION_DAYS` (mặc định 90 ngày).

### Tiered Cache Strategy (L1 Exact + L2 Semantic)

- **L1 Exact Cache**: Kiểm tra chuỗi câu hỏi đã chuẩn hóa (SHA-256 hash) trên Redis key `exact_cache:{tenant_id}:{hash}`. Tốc độ ~0.5ms, 0 token cost.
- **L2 Semantic Cache**: Nếu L1 miss, chuyển sang Vector Cosine Similarity Search với ngưỡng nghiêm ngặt `0.95` (tránh false positive cho phần mềm ERP doanh nghiệp).
- **Circuit Breaker**: Mọi sự cố kết nối Redis đều tự động bypass cache sang RAG pipeline, không làm sập request của người dùng.

### Quota & Hard Budget Enforcement

- **Cấu hình động trên Webapp**: Không hardcode giới hạn trong code. Toàn bộ quota và rate limit được đọc trực tiếp từ DB (`tenants` table: `rate_limit_rpm`, `monthly_request_quota`, `monthly_token_quota`) do Admin thiết lập từ Webapp.
- **Platform Billing & Budget Settings**: Giá token (`ai_input_price_vnd_per_1m`, `ai_output_price_vnd_per_1m`), hard budget tháng, và các ngưỡng cảnh báo được quản lý trực tiếp qua SQLite (`platform_settings` table) tại giao diện `/settings` của Platform Admin.
- **Public API Rate Limiting**: Đối với Public API (`user_id = None`), hệ thống bỏ qua kiểm tra per-user và chỉ áp dụng giới hạn duy nhất theo **Tenant** (`rate_limit_rpm` trong DB `tenants`).
- **Monthly request & token limits**: Atomic Redis counter theo tháng cho tenant dựa theo `monthly_request_quota` và `monthly_token_quota`.
- **Hard budget**: Cảnh báo ngưỡng 70%/85% và ngắt cứng (hard stop) ở ngưỡng 100% ngân sách tháng.

## Storage

| Store | Vai trò |
|---|---|
| PostgreSQL | auth, tenant, products, knowledge_bases, documents, canonical sections, conversations, usage, feedback, escalations |
| Qdrant | dual index cho retrieval |
| Redis | queue, L1 exact cache, L2 semantic cache, rate limit/quota atomic counters, audit stream |
| RustFS | file gốc và artifact ingest |
| SQLite `settings.db` | provider settings, runtime selection, và platform billing/budget settings (`platform_settings` table) |

## AI provider boundary

- LLM chính đi qua `9Router`
- Embedding local mặc định đi qua Docker Model Runner
- Reranker mặc định là NVIDIA NIM
- local reranker chỉ là fallback

Route layer không được gọi SDK/provider trực tiếp.

## Canonical section graph

Sau khi parse, tài liệu được normalize thành `document_sections` trong PostgreSQL với các field chính:

- `document_id`
- `section_id`
- `parent_section_id`
- `section_code`
- `title`
- `breadcrumb`
- `breadcrumb_text`
- `level`
- `order_index`
- `content`

Đây là source of truth cho cấu trúc tài liệu.

## Retrieval architecture

Retrieval hiện tại là **dual index + structure-aware**:

1. canonical section graph được lưu trong PostgreSQL
2. build **section index** trong Qdrant cho heading / numbered section retrieval
3. build **chunk index** trong Qdrant cho sentence-window evidence retrieval
4. filter nghiêm ngặt theo `tenant_id`
5. chuẩn hoá query (xử lý dấu câu, xoá stopword tiếng Việt, giữ nguyên ERP phrase)
6. route truy vấn:
   - section route cho numbered / heading-style query
   - semantic route cho free-form query
7. dùng `RecursiveRetriever` để mở rộng section -> chunk theo `section_id`
7. dùng `AutoMergingRetriever` để gộp nhiều chunk về parent section khi đủ tỷ lệ
8. thay sentence hit bằng local window context trước khi synthesis
9. rerank sau khi candidate đã được làm sạch theo cấu trúc
10. hydrate full section từ PostgreSQL cho top node nếu cần

### Qdrant collections

- `documents_sections`
- `documents_chunks`

### Qdrant payload

Payload chuẩn:

- `tenant_id`
- `document_id`
- `section_id`
- `section_code`
- `parent_section_id`
- `document_title`
- `heading`
- `breadcrumb_text`
- `level`
- `order_index`
- `node_kind`

## Ingestion architecture

Chi tiết luồng xử lý và các bước ingestion cụ thể, vui lòng xem tại [2.1_WORKFLOWS_INGESTION.md](./2.1_WORKFLOWS_INGESTION.md).

## Auth boundary

### Internal webapp

- browser gọi business API qua `/api/bep/*`
- Next.js route handler lấy token từ NextAuth
- backend bearer token không lộ ra browser

### Public API

- dùng `Authorization: Bearer <tenant_api_key>`
- backend tự resolve tenant từ API key
- raw key chỉ hiển thị đúng một lần lúc tạo

## Money và time

### Money

- tiền chuẩn là `VND`
- lưu dưới dạng integer `cost_micros_vnd`
- không dùng float để tính phí

### Time

- DB lưu UTC
- backend/frontend format sang `Asia/Ho_Chi_Minh` khi hiển thị

## Hard delete order

Chi tiết thứ tự xóa cứng bắt buộc (registry -> vectors -> sections -> file -> db row) vui lòng xem tại [2.3_WORKFLOWS_DELETE.md](./2.3_WORKFLOWS_DELETE.md). Mọi thay đổi về code delete phải tuân thủ nghiêm ngặt thứ tự trong tài liệu này.

## Runtime shape hiện tại

Vui lòng xem [4_DEPLOYMENT.md](./4_DEPLOYMENT.md) để biết chi tiết Topology của Docker Stack (API, Celery, Traefik, PostgreSQL, Qdrant, Redis, v.v.).
