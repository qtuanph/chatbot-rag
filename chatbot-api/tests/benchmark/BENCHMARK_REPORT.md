# Quantitative Benchmark Report: Enterprise RAG Evaluation

| Parameter | Value |
|---|---|
| **Benchmark Suite** | SAO ERP Technical Evaluation (`test_tailieukythuat.md`) |
| **Execution Timestamp** | `2026-08-13 15:41:46` |
| **Total Test Cases** | **35 questions** |
| **Corpus Sections** | **363 sections** (Parsed in 7.1 ms) |
| **Total Execution Time** | **0.95 seconds** |

---

## 1. Overall System Performance Metrics

| Metric | Measured Value | Standard Target | Status |
|---|:---:|:---:|:---:|
| **Hit Rate @ 1 (Top-1 Accuracy)** | **80.00%** | $\ge 75.0\%$ | ✅ Meets SLA |
| **Hit Rate @ 3 (Top-3 Accuracy)** | **88.57%** | $\ge 85.0\%$ | ✅ Meets SLA |
| **Hit Rate @ 5 (Top-5 Accuracy)** | **88.57%** | $\ge 85.0\%$ | ✅ Meets SLA |
| **Mean Reciprocal Rank (MRR)** | **0.833** / 1.000 | $\ge 0.800$ | ✅ Meets SLA |
| **Context Fact Recall** | **46.52%** | $\ge 40.0\%$ | ✅ Meets SLA |
| **Mean Retrieval Latency** | **27.18 ms** | $\le 50.0\text{ ms}$ | ✅ Meets SLA |
| **P50 Retrieval Latency** | **25.93 ms** | $\le 30.0\text{ ms}$ | ✅ Meets SLA |
| **P95 Retrieval Latency** | **34.85 ms** | $\le 60.0\text{ ms}$ | ✅ Meets SLA |

---

## 2. Quantitative Category Breakdown Matrix

| Category | Samples | Hit@1 (%) | Hit@3 (%) | Hit@5 (%) | MRR | Fact Recall (%) | Mean Latency (ms) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Single-hop Factoid** | 4 | **25.0%** | **50.0%** | **50.0%** | **0.33** | **50.0%** | 26.0 ms |
| **Accounting Code & Condition** | 9 | **88.9%** | **88.9%** | **88.9%** | **0.89** | **37.0%** | 26.3 ms |
| **Multi-hop / Synthesis** | 5 | **100.0%** | **100.0%** | **100.0%** | **1.00** | **40.7%** | 31.5 ms |
| **System Admin & Config** | 4 | **100.0%** | **100.0%** | **100.0%** | **1.00** | **61.7%** | 28.1 ms |
| **Semantic / Paraphrase** | 5 | **40.0%** | **80.0%** | **80.0%** | **0.57** | **6.7%** | 25.3 ms |
| **UI Navigation & Shortcuts** | 3 | **100.0%** | **100.0%** | **100.0%** | **1.00** | **37.2%** | 25.7 ms |
| **No-answer / Hallucination Trap** | 5 | **100.0%** | **100.0%** | **100.0%** | **1.00** | **100.0%** | 27.4 ms |
| **OVERALL SUMMARY** | **35** | **80.00%** | **88.57%** | **88.57%** | **0.833** | **46.52%** | **27.18 ms** |

---

## 3. Individual Test Case Execution Log

| ID | Category | Query | Matched Section | Rank | Recall | Latency | Result |
|---|---|---|---|:---:|:---:|:---:|:---:|
| `BM-01` | Single-hop Factoid | Ai là người tạo và người duyệt tài liệu hướng dẫ... | 0 Thông tin tài liệu và Phân quy... | #3 | 100% | 29.6ms | **ACCEPTABLE** |
| `BM-02` | Single-hop Factoid | Hệ thống SSE Accounting Online (SAO) được tổ chứ... | 1.1 Tổ chức các phân hệ nghiệp v... | #1 | 100% | 27.5ms | **PASS** |
| `BM-03` | Accounting Code & Condition | Trong phân hệ tiền mặt và ngân hàng, loại phiếu ... | 1.1.1.7 Thu tiền của một khách h... | #1 | 0% | 31.1ms | **FAIL** |
| `BM-04` | Accounting Code & Condition | Quy định mã loại phiếu chi từ loại 1 đến loại 4 ... | 1.1.1.14 Chi trả chi tiết theo t... | #1 | 0% | 25.6ms | **FAIL** |
| `BM-05` | Accounting Code & Condition | Mục 1.4.2 quy định về cập nhật chứng từ trùng li... | 1.4.2 Quy định về cập nhật chứng... | #1 | 100% | 32.7ms | **PASS** |
| `BM-06` | Accounting Code & Condition | Quy định xử lý chứng từ trùng trong trường hợp m... | 1.4.3 Quy định về cập nhật chứng... | #1 | 33% | 32.1ms | **FAIL** |
| `BM-07` | Multi-hop / Synthesis | Luồng dữ liệu trong SAO di chuyển như thế nào từ... | 1.1.3 Phân hệ kế toán tổng hợp | #1 | 50% | 39.9ms | **ACCEPTABLE** |
| `BM-08` | Multi-hop / Synthesis | Phân hệ kế toán hàng tồn kho nhận dữ liệu từ các... | 1.1.7 Phân hệ kế toán hàng tồn k... | #1 | 20% | 34.8ms | **FAIL** |
| `BM-09` | Multi-hop / Synthesis | Trước khi đưa phần mềm SAO vào vận hành, doanh n... | 2.1 Danh sách các công việc cần ... | #1 | 83% | 24.8ms | **PASS** |
| `BM-10` | System Admin & Config | Trường 'Mã ctừ mẹ' trong khai báo màn hình cập n... | 4.2.2 Khai báo màn hình cập nhật... | #1 | 100% | 31.0ms | **PASS** |
| `BM-11` | System Admin & Config | Phân hệ 4.6 Quản lý người sử dụng bao gồm các ch... | 4.6 Quản lý người sử dụng | #1 | 67% | 24.8ms | **ACCEPTABLE** |
| `BM-12` | System Admin & Config | Mục 4.5 Quản lý và bảo trì số liệu cung cấp nhữn... | 4.5 Quản lý và bảo trì số liệu | #1 | 80% | 28.1ms | **PASS** |
| `BM-13` | System Admin & Config | Khai báo 'Kỳ mở sổ' (mục 4.2.4) và 'Ngày đầu năm... | 4.2.3 Khai báo ngày đầu năm tài ... | #1 | 0% | 28.4ms | **FAIL** |
| `BM-14` | Semantic / Paraphrase | Tôi muốn phân quyền cho nhân viên mới vào công t... | 4.6.1 Khai báo người sử dụng và ... | #2 | 0% | 21.8ms | **FAIL** |
| `BM-15` | Semantic / Paraphrase | Làm thế nào để hiển thị và in hóa đơn bằng tiếng... | 1.9 Vấn đề giao diện và báo cáo ... | #1 | 33% | 24.9ms | **FAIL** |
| `BM-16` | Semantic / Paraphrase | Khi cần chuyển hàng từ kho tổng sang kho chi nhá... | 1.1.1.29 Các lưu ý khi nhập hóa ... | #1 | 0% | 22.5ms | **FAIL** |
| `BM-17` | Semantic / Paraphrase | Khách hàng đến mua đồ và trả bằng tiền mặt ngay ... | 1.1.1.21 Chi thanh toán chi phí ... | #3 | 0% | 23.7ms | **FAIL** |
| `BM-18` | Semantic / Paraphrase | Nếu công ty lỡ nhập sai mã khách hàng hoặc mã vậ... | None | Miss | 0% | 33.5ms | **FAIL** |
| `BM-19` | UI Navigation & Shortcuts | Các phím chức năng F2, F3, F4, F8 và F10 trên bà... | 3.2 Các phím chức năng | #1 | 20% | 31.3ms | **FAIL** |
| `BM-20` | UI Navigation & Shortcuts | Các thao tác chung khi lên báo cáo trong SAO the... | 3.7 Các thao tác chung khi lên b... | #1 | 25% | 20.6ms | **FAIL** |
| `BM-21` | Accounting Code & Condition | Các thông tin quan trọng cần lưu ý khi nhập hóa ... | 1.1.1.29 Các lưu ý khi nhập hóa ... | #1 | 75% | 24.6ms | **PASS** |
| `BM-22` | Accounting Code & Condition | Chức năng tạm ứng trước tiền hàng của khách hàng... | 1.1.1.32 Tạm ứng trước tiền hàng... | #1 | 50% | 23.8ms | **ACCEPTABLE** |
| `BM-23` | Accounting Code & Condition | SAO hỗ trợ các phương pháp tính giá hàng tồn kho... | 4.4.3 Khai báo các phương pháp t... | #1 | 0% | 18.1ms | **FAIL** |
| `BM-24` | Accounting Code & Condition | Các phương pháp tính tỷ giá ghi sổ ngoại tệ được... | 1.1.1.23 Lựa chọn phương pháp tí... | #1 | 75% | 22.6ms | **PASS** |
| `BM-25` | Single-hop Factoid | Số điện thoại hotline và địa chỉ email hỗ trợ kỹ... | None | Miss | 0% | 21.9ms | **FAIL** |
| `BM-26` | Single-hop Factoid | Chi nhánh phía Nam của công ty phần mềm SSE đặt ... | None | Miss | 0% | 24.8ms | **FAIL** |
| `BM-27` | Multi-hop / Synthesis | SAO giải quyết bài toán quản lý số liệu của các ... | 1.8 Vấn đề quản lý số liệu của đ... | #1 | 25% | 32.2ms | **FAIL** |
| `BM-28` | Multi-hop / Synthesis | Phân hệ kế toán TSCĐ và phân hệ kế toán CCDC khá... | 1.1.9 Phân hệ kế toán công cụ dụ... | #1 | 25% | 25.7ms | **FAIL** |
| `BM-29` | UI Navigation & Shortcuts | Quy tắc nhập tài khoản kế toán trong SAO (mục 3.... | 3.8 Các thức nhập tài khoản | #1 | 67% | 25.1ms | **ACCEPTABLE** |
| `BM-30` | Accounting Code & Condition | Phiếu chi loại 8 trong phân hệ tiền mặt và ngân ... | None | Miss | 0% | 26.4ms | **FAIL** |
| `BM-31` | No-answer / Hallucination Trap | Chính sách nghỉ thai sản và mức trợ cấp thôi việ... | Correctly Guarded Against Halluc... | #1 | 100% | 28.5ms | **PASS** |
| `BM-32` | No-answer / Hallucination Trap | Bảng giá cước phí thuê máy chủ Cloud server và d... | Correctly Guarded Against Halluc... | #1 | 100% | 25.9ms | **PASS** |
| `BM-33` | No-answer / Hallucination Trap | Báo cáo tài chính năm 2025 và chỉ số lợi nhuận s... | Correctly Guarded Against Halluc... | #1 | 100% | 32.6ms | **PASS** |
| `BM-34` | No-answer / Hallucination Trap | Hệ thống SAO có tích hợp công nghệ Smart Contrac... | Correctly Guarded Against Halluc... | #1 | 100% | 24.2ms | **PASS** |
| `BM-35` | No-answer / Hallucination Trap | Dự báo thời tiết và nhiệt độ tại Hà Nội và TP.HC... | Correctly Guarded Against Halluc... | #1 | 100% | 25.9ms | **PASS** |

---
*Report auto-generated by `tests/benchmark/run_benchmark.py`.*
