# Release Notes - Lịch sử Phát hành

Tổng hợp lịch sử phát hành của hệ thống RAG đa doanh nghiệp (SaaS Multi-tenant).

---

## 🚀 v0.8.2 (Hiện tại)
*Nâng cấp bảo mật các thư viện phụ thuộc.*
- Cập nhật phiên bản thư viện `js-yaml` từ `4.1.1` lên `4.3.0` để bảo mật an toàn hệ thống.

---

## 🚀 v0.8.0
*Nâng cấp tài liệu Tích hợp phần mềm & API Playground.*
- **API Playground trực tuyến**: Hỗ trợ thử nghiệm gọi RAG API trực tiếp từ giao diện tài liệu bằng cách nhập API Key (`trg_...`).
- **Thiết kế phẳng (Flat Layout)**: Thay đổi Accordion sang các khối độc lập.
- **Dynamic Theme support**: Sử dụng CSS variables của Shadcn/Base UI, tự động đổi màu theo Light/Dark mode.
- **Dọn dẹp Backend**: Loại bỏ endpoint custom `/chat/stream` thừa, sử dụng duy nhất `/v1/chat/completions` chuẩn OpenAI.

---

## 🚀 v0.7.0
*Đồng bộ tài liệu hướng dẫn và cập nhật settings.*
- Cập nhật các tệp tin trong `docs/` để đồng bộ với cấu hình môi trường runtime.

---

## 🚀 v0.6.3
*Nâng cấp Analytics Dashboard UI & Tối ưu AI pipeline.*
- **Analytics Dashboard**: Nâng cấp giao diện biểu đồ và quản trị.
- **User Settings**: Form giao diện điều chỉnh thông số chatbot và hiệu ứng chữ gõ (typing effect).
- **AI pipeline**: Cải tiến luồng băm dữ liệu Embedding và Reranker.

---

## 🚀 v0.6.2
*Bump dependencies tự động.*
- Cập nhật các gói thư viện Python và npm để cải thiện bảo mật và vá lỗi.

---

## 🚀 v0.6.1
*Theo dõi độ trễ AI model & Token usage.*
- Bổ sung tracking model latency (độ trễ phản hồi) và số token embedding sử dụng thực tế.

---

## 🚀 v0.6.0
*Tái cấu trúc utils & Tối ưu semantic cache.*
- Refactor cấu trúc thư mục tiện ích backend và tăng tốc độ trả lời nhờ bộ đệm tương đồng ngữ nghĩa.

---

## 🚀 v0.5.2
*Hoàn tất tích hợp Cloudflare (Production-ready).*
- Chuyển đổi middleware sang Edge runtime để tương thích với Cloudflare Next-on-Pages.
- Tối ưu hóa kích thước bundle và tắt cache component tạm thời để tránh lỗi EISDIR.

---

## 🚀 v0.5.1
*Sửa lỗi build Cloudflare & Cập nhật tài liệu.*
- Sửa lỗi tương thích linter, tooltip mismatch, và cập nhật tài liệu hướng dẫn cho BA & Dev.

---

## 🚀 v0.5.0
*Refactor UI quản lý AI Providers.*
- Chia nhỏ các tab cài đặt AI Providers (Embedding, Reranker, LLM) thành các router tĩnh.
