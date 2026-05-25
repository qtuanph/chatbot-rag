# KẾ HOẠCH NÂNG CẤP HỆ THỐNG RAG CHATBOT (PHẦN CỨNG & PHẦN MỀM - 2026)

Tài liệu này tổng hợp toàn bộ kế hoạch nâng cấp stack công nghệ lên phiên bản mới nhất năm 2026, sửa lỗi bảo mật nghiêm trọng, tối ưu hóa hiệu năng/concurrency cho hệ thống 200+ CCU, khắc phục các vấn đề về mã hóa tiếng Việt/mojibake, và chuẩn bị vận hành tối ưu với Qdrant.

---

## 1) Mục tiêu cốt lõi
1. **Up-to-date 2026**: Nâng cấp toàn bộ package và container lên phiên bản an toàn, ổn định mới nhất tính đến tháng 5/2026.
2. **Không lỗi mã hóa**: Khắc phục triệt để các chuỗi mojibake (ví dụ: `â†’`) và Việt hóa có dấu chuẩn xác cho toàn bộ thông báo hệ thống.
3. **Bảo mật & Rate limit**: Khóa các lỗ hổng rò rỉ thông tin admin và sửa lỗi hệ thống Rate Limiter hoạt động sai cách.
4. **Hiệu năng & Concurrency**: Giải phóng các điểm nghẽn cổ chai (embedding semaphore=1, sequential ingestion) và ngăn chặn việc chặn đứng async event loop (sync subprocess/sync db calls).
5. **Giữ Qdrant ở bản `:latest` (Theo đề xuất của User)**: Chấp nhận giữ tag `:latest` (hiện tại tương ứng với v1.18.1), nhưng thiết lập quy trình kiểm tra độ tương thích của API client trước khi triển khai thực tế.
6. **MANDATORY - Scan kỹ codebase trước khi sửa**: Thực hiện quét chi tiết cấu trúc tập tin, bảng mã hóa (encoding), và các phụ thuộc trực tiếp để tránh làm gãy luồng hoạt động hiện tại.

---

## 2) Đánh giá và Đề xuất nâng cấp Stack Công nghệ (2026)

| Thành phần | Phiên bản hiện tại | Đề xuất nâng cấp (2026) | Ghi chú / Lý do |
|:---|:---|:---|:---|
| **FastAPI** | `0.136.1` | **`0.136.3`** | Phiên bản mới nhất (23/05/2026), sửa các lỗi bảo mật nhỏ và tối ưu router. |
| **SQLAlchemy** | `2.0.49` | **`2.0.50`** | Phiên bản ổn định mới nhất (24/05/2026). |
| **Qdrant Server** | `latest` | **`latest`** (Giữ nguyên) | Chấp nhận chạy bản mới nhất (v1.18.1). Cần đảm bảo `qdrant-client` hỗ trợ đầy đủ các API mới nhất. |
| **PostgreSQL** | `18.4-trixie` | **`18.4-trixie`** (Giữ nguyên) | Giữ nguyên phiên bản trixie theo yêu cầu trực tiếp của User. |
| **Redis Server** | `8-alpine` | **`8.6.3-trixie`** | Chuyển sang `redis:8.6.3-trixie` theo đề xuất của User. |
| **Redis Client (py)** | `7.4.0` | **`7.4.0`** | Giữ nguyên vì đây đã là phiên bản mới nhất hiện tại của `redis-py`. |
| **Traefik** | `v3.7.1` | **`v3.7.3`** | Sửa các lỗi bảo mật định tuyến và tối ưu hóa TLS. |

---

## 3) Nguyên tắc Quét (Scan) kỹ Codebase trước khi sửa đổi

Để đảm bảo an toàn tuyệt đối cho hệ thống đang chạy ổn định, trước khi thực hiện bất kỳ thay đổi nào vào mã nguồn, ta phải tuân thủ quy trình quét (scan) bắt buộc sau:

1. **Quét định dạng mã hóa (Encoding & Line Endings)**:
   - Quét toàn bộ các file nguồn bằng công cụ phân tích để đảm bảo tất cả đều lưu ở định dạng **UTF-8 (no BOM)** và sử dụng xuống dòng kiểu **LF** (`\n`).
   - Tuyệt đối không lưu đè hoặc sửa đổi bằng các chương trình tự động chuyển về CRLF (Windows).
2. **Quét sự phụ thuộc của LlamaIndex & Qdrant-Client**:
   - Trước khi sửa các hàm gọi đến `vector_store._aclient` và `_sparse_query_fn`, cần quét xem client library `qdrant-client` và `llama-index-vector-stores-qdrant` có những API public nào thay thế an toàn hơn cho các hàm nội bộ này, tránh dùng lại thuộc tính private.
3. **Quét luồng xử lý đồng bộ (Sync) trong các hàm Async**:
   - Quét tất cả các file trong `app/modules/documents/ingestion/` và `app/modules/chat/` để tìm tất cả các lệnh gọi blocking I/O (như `subprocess.run`, `sqlite3.connect`, các query SQL synchronous, các hàm thư viện Redis sync) đang nằm trong luồng `async def`. Tất cả phải được bọc bằng `asyncio.to_thread`.
4. **Kiểm tra chéo cấu hình biến môi trường**:
   - Quét file `.env` và `app/core/config.py` để đảm bảo không có biến môi trường nào bị cấu hình chồng chéo hoặc thiếu sót sau khi nâng cấp phiên bản các thư viện.

---

## 4) Chi tiết các lỗ hổng & Điểm nghẽn cần sửa đổi

### A. Lỗ hổng Bảo mật & API Gaps
1. **Lỗ hổng phân quyền Admin (`app/modules/admin/router.py`)**:
   - *Chi tiết*: Các route `GET /admin/models` và `GET /admin/usage/daily` hoàn toàn không kiểm tra token hoặc quyền admin (không có `Depends(get_auth_context)`). Bất kỳ ai ngoài internet cũng có thể gọi và đọc cấu hình proxy, chi phí token hàng ngày.
   - *Giải pháp*: Nhúng middleware kiểm tra quyền admin vào toàn bộ route thuộc admin module.
2. **Lỗi logic RateLimiter Middleware (`app/api/middleware.py` L180)**:
   - *Chi tiết*: Middleware gọi `r_client = get_redis_client()` nhưng không `await`. Vì `get_redis_client()` từ `app.core.redis` là sync function trả về đối tượng Async Redis client, việc sử dụng nó trực tiếp mà không cấu hình đúng hoặc nhầm lẫn loop khiến RateLimiter liên tục báo lỗi và rơi vào block `except Exception` -> mặc định cho qua (`allowed = True`).
   - *Giải pháp*: Fix lại cách khởi tạo `RateLimiter` và `r_client` trong middleware để tránh coroutine mismatch.
3. **Thiếu Rate Limiting ở chat endpoint `/chat/stream`**:
   - *Chi tiết*: Đây là API tốn kém nhất nhưng không hề có rate limit ở mức endpoint, chỉ dựa vào global middleware vốn bị tắt ở dev/staging.
   - *Giải pháp*: Thêm `get_rate_limiter` kiểm soát tần suất chat của từng user.

### B. Hiệu năng & Blockers hệ thống (Concurrency & Loop Blocking)
1. **Nút thắt cổ chai Embedding Semaphore (`app/core/llama_index.py` L17)**:
   - *Chi tiết*: Khai báo `_embed_async_semaphore = asyncio.Semaphore(1)` bắt mọi tác vụ sinh embedding (cả khi chat lẫn khi ingest file) phải xếp hàng tuần tự 1-by-1. Khi có nhiều người chat cùng lúc hoặc nhiều file đang xử lý, hệ thống sẽ bị nghẽn nghiêm trọng.
   - *Giải pháp*: Nâng cấu hình semaphore lên `8` hoặc gỡ bỏ (để TEI tự cân bằng tải qua config của nó).
2. **Sequential Ingestion (`app/modules/documents/ingestion/pipeline.py` L123-173)**:
   - *Chi tiết*: Tiến trình chạy `batch_size = 1` và `num_workers = 1` khiến việc chia nhỏ văn bản và đẩy lên Qdrant chạy cực kỳ chậm chạp.
   - *Giải pháp*: Đổi sang xử lý song song với `num_workers = settings.embed_parallelism`.
3. **Chặn đứng Event Loop khi chuyển đổi DOCX -> PDF**:
   - *Chi tiết*: `ingestion_service.py` gọi hàm `convert_docx_to_pdf` chứa lệnh đồng bộ `subprocess.run(..., timeout=120)`. Việc này sẽ block hoàn toàn event loop của FastAPI trong tối đa 2 phút, khiến tất cả người dùng khác đang kết nối bị đứng hình.
   - *Giải pháp*: Bọc lệnh convert bằng `asyncio.to_thread` hoặc chạy qua Celery task tách biệt hoàn toàn.
4. **Lạm dụng Redis `KEYS` trên luồng xử lý chính**:
   - *Chi tiết*: Hàm `_clear_cache_for_dislike` trong `service.py` gọi `client.keys("cache:semantic:*")`. Lệnh `KEYS` có độ phức tạp O(N) và block Redis server đơn luồng. Tương tự trong `cleanup_service.py:58`.
   - *Giải pháp*: Thay thế hoàn toàn bằng `scan_iter()`.
5. **Rò rỉ Socket Pool từ sync Redis Client (`app/core/redis.py` L66)**:
   - *Chi tiết*: `get_sync_redis_client()` tạo mới một `ConnectionPool` trên mỗi lần gọi thay vì tái sử dụng. Khi hệ thống ghi log audit liên tục, nó sẽ tạo ra hàng ngàn pool và làm cạn kiệt socket của hệ điều hành.
   - *Giải pháp*: Lưu pool dạng singleton/module-level variable để tái sử dụng.

### C. Lỗi logic & Lỗi mã hóa (Bug & Encoding)
1. **Lỗi logic làm hỏng đếm vector trong Recovery (`app/modules/documents/ingestion/recovery_service.py`)**:
   - *Chi tiết*: Dòng code `len(await self.vector_store.adelete(ref_doc_id=document_id))` ném ra ngoại lệ `TypeError: object of type 'NoneType' has no len()` vì `adelete` trả về `None`. Ngoại lệ bị catch âm thầm và gán `vector_count = 0`. Điều này làm báo cáo khôi phục luôn trả về 0 vector.
   - *Giải pháp*: Sửa lại logic gọi `adelete` và đếm thực tế.
2. **Truy cập thuộc tính private của thư viện**:
   - *Chi tiết*: Mã nguồn sử dụng `vector_store._aclient` và `vector_store._sparse_query_fn` trực tiếp. Các thuộc tính bắt đầu bằng `_` này có thể bị đổi tên ở bất kỳ phiên bản nâng cấp nào của LlamaIndex làm crash tính năng tìm kiếm.
   - *Giải pháp*: Chuyển sang sử dụng API public được tài liệu hóa.
3. **Lỗi mã hóa tiếng Việt & Mojibake**:
   - *Chi tiết*: Các file như `ingestion_service.py` chứa ký tự lỗi hiển thị `â†’` thay vì mũi tên `→`. Ngoài ra, các chuỗi ghi log tiến trình bị viết không dấu (ví dụ: `Dang bat dau embedding va ghi du lieu vao Qdrant...`).
   - *Giải pháp*: Sửa toàn bộ thành tiếng Việt có dấu chuẩn UTF-8 và chuyển đổi ký tự lỗi thành dạng chuẩn.

---

## 5) Phân rã Kế hoạch Thực hiện (Các Phase Chi tiết)

### Phase 1: Sửa lỗi mã hóa + Tiếng Việt + Dọn dẹp Mojibake (P0)
- Quét và sửa lỗi mã hóa ký tự `â†’` thành `→` trong `ingestion_service.py`.
- Việt hóa có dấu toàn bộ các chuỗi log tiến trình hiển thị cho user.
- Thêm cơ chế kiểm tra định dạng dòng kết thúc (LF) và Encoding (UTF-8 no BOM) trong Git hooks hoặc CI.

### Phase 2: Nâng cấp Stack Công nghệ & Pin Docker Images (P0)
- Nâng cấp `FastAPI` lên `0.136.3` và `SQLAlchemy` lên `2.0.50` trong `requirements.txt`.
- Cập nhật `docker-compose.yml`:
  - `postgres:18.4-trixie` (Giữ nguyên theo yêu cầu)
  - `redis:8.6.3-trixie` (Theo đề xuất của User)
  - `traefik:v3.7.3`
  - *Lưu ý*: Giữ nguyên `qdrant/qdrant:latest` theo yêu cầu của User.
- Chạy thử local, kiểm tra tính tương thích và bảo đảm hệ thống khởi động bình thường.

### Phase 3: Vá lỗi Bảo mật & Rate Limit (P0)
- Áp dụng kiểm tra Token & Role Admin cho `/admin/models` và `/admin/usage/daily`.
- Sửa lỗi không `await` coroutine trong `RateLimitMiddleware`.
- Bổ sung cấu hình rate limit cho chat stream endpoint `/chat/stream`.

### Phase 4: Tối ưu hóa Hiệu năng & Giải phóng Event Loop (P1)
- Cập nhật semaphore trong `app/core/llama_index.py` từ `1` lên `8`.
- Cấu hình parallel workers cho ingestion pipeline qua `settings.embed_parallelism` (nếu > 0) hoặc tự động giới hạn ở mức an toàn `min(4, hardware.embed_parallelism)` để tối ưu tài nguyên.
- Chuyển subprocess chuyển đổi Word -> PDF sang chạy non-blocking qua `asyncio.to_thread`.
- Thay thế toàn bộ `client.keys()` bằng `client.scan_iter()`.
- Sửa hàm `get_sync_redis_client()` tái sử dụng connection pool.

### Phase 5: Sửa lỗi Logic Recovery & Clean up (P1)
- Xóa bỏ lỗi đếm `len(None)` trong `recovery_service.py` khi xóa vector.
- Bọc các truy vấn Qdrant sync trong `recovery_service.py` bằng `asyncio.to_thread`.
- Thiết lập bộ lọc `"document_id"` duy nhất trong Qdrant để đồng bộ tuyệt đối với trường dữ liệu trong ingestion metadata, loại bỏ bộ lọc `should` vá tạm thời.
- Giới hạn thời gian poll LlamaParse tránh bị lặp vô hạn.

### Phase 6: Đồng bộ hóa Tài liệu (P2)
- Cập nhật các file:
  - `docs/7_CURRENT_SETTINGS.json`
  - `docs/4_DEPLOYMENT.md`
  - `docs/6_KNOWN_ISSUES.json`
- Chạy pre-commit linting:
  ```bash
  python -m black app --line-length=120
  python -m flake8 app --select=F,E1,E2,E4,E9,W --ignore=E203,E501,W293,W292,W391,W503,W504
  ```

---

## 6) Tiêu chí nghiệm thu (Definition of Done)
1. **Không lỗi linting**: Lệnh kiểm tra code chạy thành công với mã thoát (exit code) = `0`.
2. **An toàn bảo mật**: Gọi thử `/api/v1/admin/models` không kèm token bắt buộc phải trả về `401 Unauthorized` hoặc `403 Forbidden`.
3. **Hiệu năng thực tế**: Kiểm tra log API khi chạy đồng thời nhiều lượt chat, thời gian chờ embedding phải giảm rõ rệt và không còn tình trạng nghẽn hàng đợi (waiting semaphore).
4. **Không rò rỉ socket**: Theo dõi số lượng connection của Redis trong quá trình chạy test và ghi log, không tăng đột biến vô tận.
5. **Tiếng Việt chính xác**: Toàn bộ tiến trình hiển thị đúng tiếng Việt có dấu, không dính ký tự lạ.
