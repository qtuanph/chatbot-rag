---
name: feedback
description: Database credentials structure - PostgreSQL admin vs app user passwords
type: feedback
---

# Database Credentials Structure - CRITICAL

## QUAN TRỌNG: Tôi đã NHẦU nhiều lần về password!

### Cấu trúc ĐÚNG:

**PostgreSQL Setup (via docker-compose.yml):**
```yaml
environment:
  POSTGRES_DB=ragbot
  POSTGRES_USER=db-admin          # PostgreSQL ADMIN account
  POSTGRES_PASSWORD=replace-me    # Password cho db-admin
  app.app_rw_password=${APP_DB_PASSWORD:-replace-me}  # App user password
```

**Application Connection (.env):**
```bash
DATABASE_URL=postgresql+psycopg://app_rw:replace-me@db:5432/ragbot
APP_DB_USER=app_rw
APP_DB_PASSWORD=replace-me
```

### Key Points:

1. **PostgreSQL Admin** (`db-admin`):
   - Password quản lý bởi PostgreSQL container
   - Không cần lưu trong .env
   - Dùng cho database management tasks

2. **App User** (`app_rw`):
   - Password trong `.env` (`APP_DB_PASSWORD`)
   - Được truyền vào PostgreSQL container qua environment variable
   - App dùng password này để connect

### ❌ NHỮNG LỖI TÔI ĐÃ MẮC:

1. ❌ Generate strong passwords MỚI cho `.env` trong khi database volume CŨ đang dùng password CŨ
2. ❌ Không hiểu rằng PostgreSQL container đã được init với password từ lần chạy TRƯỚC
3. ❌ Khi recreate database volume, cần phải **down -v** và prune volumes mới thực sự delete

### ✅ ĐỂ TRÁNH LẦM:

**Khi thay đổi password trong .env:**
```bash
# SAU KHI THAY ĐỔI .env:
docker compose down -v              # Stop + remove volumes
docker volume prune -f               # Prune unused volumes
docker compose up -d                 # Start with fresh volumes
```

**Khi database volume đã tồn tại:**
- Password trong `.env` PHẢI khớp với password đã tạo container LẦN ĐẦU
- HOẶC phải recreate volume (xóa data)

### Production Deployment:
- Nên dùng strong passwords
- Tạo database volume **LẦN ĐẦU** với strong passwords
- Store credentials in secrets manager (NOT in .env)

## Last Updated
- 2026-04-13: Created after multiple password confusion mistakes
