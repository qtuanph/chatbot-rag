## Pre-Release Checklist

### 1) Code & Quality
- [ ] `git status` sạch, không còn thay đổi ngoài ý muốn
- [ ] Đã rebase/pull mới nhất từ `main`
- [ ] Không còn TODO/FIXME critical
- [ ] Lint/format pass

### 2) Tests
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual smoke test: auth, upload, ingestion, chat, delete
- [ ] Kiểm tra mobile UI (chat + sidebar + form chính)

### 3) Security
- [ ] Không lộ secret trong code/docs/history mới
- [ ] Secret scan pass (Gitleaks/GitGuardian)
- [ ] Dependency scan không có mức `high/critical` chưa xử lý
- [ ] `.env.example` không chứa key thật

### 4) Data & Infra
- [ ] Xác nhận strategy volume/cache (giữ/xóa gì trước deploy)
- [ ] Xác nhận collection/vector DB tồn tại và hoạt động
- [ ] Xác nhận Redis/Celery/Worker healthy
- [ ] Xác nhận route/reverse-proxy hoạt động (localhost + domain nếu có)

### 5) Docs Sync (bắt buộc)
- [ ] `docs/3_API_CONTRACTS.md` (nếu đổi API)
- [ ] `docs/4_DEPLOYMENT.md` (nếu đổi runtime/compose)
- [ ] `docs/7_CURRENT_SETTINGS.json` (nếu đổi config mặc định)
- [ ] `docs/6_KNOWN_ISSUES.json` (nếu có fix bug quan trọng)

### 6) Release Process
- [ ] Tạo tag semantic version `vMAJOR.MINOR.PATCH`
- [ ] Soạn release notes theo `.github/RELEASE_TEMPLATE.md`
- [ ] Tạo PR release vào `main`
- [ ] CI xanh toàn bộ trước khi merge
- [ ] Verify sau merge: tag, release, branch cleanup

### 7) Post-Release
- [ ] Theo dõi logs 15-30 phút đầu
- [ ] Kiểm tra analytics token/cost/latency có ghi nhận
- [ ] Ghi nhanh rollback note nếu phát sinh sự cố

