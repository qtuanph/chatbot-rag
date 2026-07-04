# Release Notes - v0.8.0

Hệ thống RAG đa doanh nghiệp (SaaS Multi-tenant) cập nhật nâng cấp kiến trúc API và tối ưu tài liệu hướng dẫn vận hành.

## 🚀 Tính năng mới &amp; Cải tiến giao diện

### 1. Nâng cấp tài liệu Tích hợp phần mềm &amp; API Playground
- **Nhúng Live Chat Playground trực tuyến**: Hỗ trợ thử nghiệm gọi RAG API trực tiếp từ giao diện tài liệu bằng cách nhập API Key (`trg_...`) của Tenant. Trực quan hóa tiến trình stream tokens của model trong thời gian thực.
- **Thiết kế phẳng (Flat Layout) chuẩn Base UI**: Loại bỏ cấu hình Accordion lồng nhau phức tạp. Mỗi bước tích hợp hiện là một khối collapsible độc lập và sạch sẽ.
- **Dynamic Theme support**: Loại bỏ hoàn toàn mã màu hardcode (`bg-blue-600`, `text-indigo-600`...). Toàn bộ styles sử dụng CSS variables mặc định của Shadcn/Base UI, tự động thay đổi mượt mà theo giao diện Sáng/Tối (Light/Dark mode).

### 2. Chuẩn hóa &amp; Chi tiết hóa trang Giới thiệu chung
- Bổ sung **Sơ đồ Kiến trúc phân lớp hệ thống** (Client App → API Backend → Celery Workers → DB &amp; Vector DB → AI Services).
- Làm rõ quy trình **Semantic Chunking** và băm vector.
- Trình bày trực quan quy tắc **Hard-Delete Order** (strict rule) bảo vệ tính toàn vẹn dữ liệu.

---

## 🛠 Tái cấu trúc &amp; Dọn dẹp Code thừa (Refactoring)

### Backend (`chatbot-api`)
- **Xóa bỏ endpoint custom `/chat/stream`**: Toàn bộ hệ thống giờ đây chỉ expose duy nhất route chuẩn tương thích với OpenAI là `/v1/chat/completions` (Direct API Call).
- **Giữ lại `/chat/feedback`**: Hỗ trợ thu thập feedback của người dùng để cải tiến hệ thống.

### Webapp (`chatbot-webapp`)
- Xóa bỏ hoàn toàn trang Chat Test nội bộ `/chat` lỗi thời và các component phụ thuộc.
- Cập nhật Sidebar gỡ liên kết trang Chat Test cũ.
- Chạy type-check `npx tsc --noEmit` thành công 100% không còn lỗi cú pháp hay linter.
