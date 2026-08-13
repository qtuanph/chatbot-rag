# 🧪 SAO ERP Benchmark & Evaluation Suite

Bộ công cụ đánh giá định lượng năng lực hệ thống **Enterprise RAG (Chatbot-RAG)** dựa trên tài liệu nghiệp vụ phần mềm kế toán SSE Accounting Online (`test_tailieukythuat.md`).

## 📁 Cấu trúc Thư mục

- [`sao_erp_benchmark_dataset.json`](./sao_erp_benchmark_dataset.json): Bộ dữ liệu kiểm thử gồm **35 câu hỏi thực tế** được đóng vai bởi các Persona (Kế toán trưởng, Kế toán thanh toán, Kế toán kho, Quản trị hệ thống, Người dùng mới, v.v.) chia thành 7 nhóm thử thách.
- [`run_benchmark.py`](./run_benchmark.py): Công cụ chạy tự động toàn bộ bài thi, đo lường các chỉ số Hit@1, Hit@3, Hit@5, MRR, Recall, Latency và xuất báo cáo.
- [`BENCHMARK_REPORT.md`](./BENCHMARK_REPORT.md): Báo cáo kết quả chi tiết kèm bảng điểm định lượng, sẵn sàng trích xuất số liệu đưa vào **CV / Portfolio / GitHub README**.
- [`benchmark_results.json`](./benchmark_results.json): Dữ liệu kết quả dạng JSON có cấu trúc.

## 🚀 Cách chạy Benchmark

Tại thư mục `chatbot-api/`, thực hiện lệnh:

```bash
python tests/benchmark/run_benchmark.py
```

## 📊 Các nhóm Persona & Câu hỏi kiểm thử

1. **Single-hop Factoid** (Ban Giám đốc / Kiểm toán): Tra cứu thông tin tác giả, người duyệt, trụ sở, chi nhánh.
2. **Accounting Code & Condition** (Kế toán viên): Các mã loại phiếu thu 1-9, phiếu chi 1-9, hạch toán tạm ứng, tỷ giá ghi sổ.
3. **Multi-hop / Synthesis** (Kế toán trưởng / CFO): Luồng luân chuyển chứng từ từ phân hệ cơ sở sang kế toán tổng hợp, 9 bước chuẩn bị vận hành ERP.
4. **System Admin & Config** (IT Admin): Khai báo mã chứng từ mẹ, phân quyền người dùng, kỳ mở sổ, khóa sổ, sao lưu backup.
5. **Semantic / Paraphrase** (Người dùng đời thường): Câu hỏi dùng từ ngữ giao tiếp tự nhiên không trùng khớp tiêu đề tài liệu.
6. **UI Navigation & Shortcuts** (Người dùng mới): Các phím tắt F2, F3, F4, F8, F10, quy tắc nhập tài khoản kế toán.
7. **No-answer / Hallucination Trap** (Bẫy ảo giác): Các câu hỏi không có trong tài liệu (Blockchain, AI camera chấm công, thời tiết, giá cước 2026).
