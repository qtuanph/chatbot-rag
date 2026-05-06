# Known Issues & Troubleshooting

Tài liệu này lưu trữ các lỗi kinh điển đã từng xảy ra trong quá trình phát triển dự án RAG Chatbot, nguyên nhân cốt lõi và cách khắc phục để tránh lặp lại trong tương lai.

## 1. Celery Task: `RuntimeError: Event loop is closed`

### Triệu chứng (Symptom)
Khi thực hiện các tác vụ ngầm thông qua Celery (ví dụ: `delete_document_task`), log của worker (`butler`) hiển thị lỗi `RuntimeError: Event loop is closed` ngay tại các dòng gọi đến `redis_client`, `DocumentRegistry`, hoặc các thao tác I/O bất đồng bộ (async).

Hậu quả: Tác vụ bị ngắt giữa chừng, dữ liệu không được xóa sạch (ví dụ tài liệu chỉ được đánh dấu `deleted` nhưng vẫn còn trong DB).

### Nguyên nhân (Root Cause)
Lỗi xảy ra do sự xung đột giữa cơ chế quản lý tiến trình của Celery và cơ chế Event Loop của Asyncio:
1. Các singleton như `redis_client` được khởi tạo ở cấp độ module (module-level) khi worker vừa start.
2. Khi Celery gọi một task, chúng ta sử dụng `asyncio.run(_delete_async())` để chạy code bất đồng bộ trong môi trường đồng bộ.
3. `asyncio.run()` tạo ra một Event Loop **hoàn toàn mới**.
4. Khi code bên trong loop mới cố gắng sử dụng `redis_client` (hoặc `DocumentRegistry` chứa nó), Redis client lại đang nắm giữ reference tới cái loop cũ (loop đã bị đóng hoặc không tương thích), dẫn đến crash hệ thống.

### Cách khắc phục (Resolution)
**Tuyệt đối KHÔNG** sử dụng các async client (như `redis_client`) được khởi tạo ở cấp module bên trong các task Celery dùng `asyncio.run()`.

Thay vào đó, áp dụng cơ chế **Cấp phát cục bộ (Local Instantiation)**:
1. Đảm bảo `app.core.redis` cung cấp một hàm sinh client mới, ví dụ: `get_redis_client()`.
2. Khởi tạo client và các dịch vụ phụ thuộc **ngay bên trong** hàm async được chạy bởi `asyncio.run()`.

**Ví dụ Code Fix:**
```python
# SAI: Khởi tạo bên ngoài, dính loop cũ
# registry = DocumentRegistry(redis_client) 

async def _delete_async():
    # ...

cleanup_result, verify = asyncio.run(_delete_async())
```

```python
# ĐÚNG: Khởi tạo bên trong loop mới
async def _delete_async():
    from app.core.redis import get_redis_client
    local_redis = get_redis_client()
    registry = DocumentRegistry(local_redis)
    
    # Patch vào các module khác nếu chúng dùng chung registry
    import app.services.retrieval.retrieval_service as rs
    rs.registry = registry

    # ... tiến hành logic ...

cleanup_result, verify = asyncio.run(_delete_async())
```

### Bài học rút ra
*   Cẩn trọng khi kết hợp `asyncio.run()` với các biến toàn cục (global variables) liên quan đến I/O (Database, Redis, Qdrant).
*   Luôn nhớ rằng `asyncio.run()` luôn tạo ra một "vũ trụ" Event Loop mới, mọi thứ đi vào vũ trụ đó đều phải được "sinh ra" trong nó để đảm bảo an toàn.
