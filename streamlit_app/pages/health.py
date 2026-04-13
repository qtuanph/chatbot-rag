"""
Health monitoring page for Streamlit app (admin only).
"""
import streamlit as st
import time
from components.auth import check_authentication, check_admin_role, logout
from components.api_client import api_client

# Configure page
st.set_page_config(
    page_title="Sức khỏe hệ thống",
    page_icon="🏥",
    layout="wide"
)

# Check authentication and admin role
if not check_authentication():
    st.stop()

if not check_admin_role():
    st.error("Bạn không có quyền truy cập trang này.")
    st.stop()

# Sidebar
with st.sidebar:
    st.title(f"👤 {st.session_state.get('username', 'User')}")
    st.caption(f"Vai trò: {st.session_state.get('user_role', 'member').title()}")

    st.markdown("---")

    # Navigation
    if st.button("💬 Chat", use_container_width=True):
        st.switch_page("pages/chat.py")
    if st.button("📄 Tài liệu", use_container_width=True):
        st.switch_page("pages/documents.py")
    if st.button("🌳 Cây tài liệu", use_container_width=True):
        st.switch_page("pages/tree.py")
    if st.button("🏥 Sức khỏe hệ thống", use_container_width=True):
        st.switch_page("pages/health.py")
    if st.button("👥 Quản lý người dùng", use_container_width=True):
        st.switch_page("pages/users.py")

    st.markdown("---")
    if st.button("🚪 Đăng xuất", use_container_width=True):
        logout()
        st.switch_page("pages/login.py")

# Main content
st.title("🏥 Sức khỏe hệ thống")

# Auto-refresh setting
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("### 📊 Tổng quan hệ thống")
with col2:
    auto_refresh = st.checkbox("Tự động làm mới (30s)", value=True)

# Fetch health data
health_data = api_client.get("/api/v1/health/data")

if health_data:
    # Overall status
    overall_status = health_data.get("overall_status", "unknown")
    status_emoji = {
        "healthy": "✅",
        "degraded": "⚠️",
        "unhealthy": "❌"
    }.get(overall_status, "❓")

    st.markdown(f"### {status_emoji} Trạng thái tổng quát: **{overall_status.upper()}**")
    st.markdown("---")

    # Services section
    st.markdown("#### 🔧 Trạng thái dịch vụ")

    services = health_data.get("services", {})

    # Display service cards
    col1, col2, col3 = st.columns(3)
    with col1:
        db_status = services.get("database", {})
        db_emoji = "✅" if db_status.get("status") == "healthy" else "❌"
        st.metric(f"{db_emoji} Database", db_status.get("status", "unknown").upper())
        if db_status.get("details"):
            st.caption(db_status.get("details", ""))

    with col2:
        qdrant_status = services.get("qdrant", {})
        qdrant_emoji = "✅" if qdrant_status.get("status") == "healthy" else "❌"
        st.metric(f"{qdrant_emoji} Qdrant", qdrant_status.get("status", "unknown").upper())
        if qdrant_status.get("details"):
            st.caption(qdrant_status.get("details", ""))

    with col3:
        redis_status = services.get("redis", {})
        redis_emoji = "✅" if redis_status.get("status") == "healthy" else "❌"
        st.metric(f"{redis_emoji} Redis", redis_status.get("status", "unknown").upper())
        if redis_status.get("details"):
            st.caption(redis_status.get("details", ""))

    st.markdown("---")

    # Storage section
    st.markdown("#### 💾 Môi trường lưu trữ")

    storage = health_data.get("storage", {})

    col1, col2 = st.columns(2)
    with col1:
        rustfs_status = storage.get("rustfs", {})
        rustfs_emoji = "✅" if rustfs_status.get("status") == "healthy" else "❌"
        st.metric(f"{rustfs_emoji} RustFS", rustfs_status.get("status", "unknown").upper())
        if rustfs_status.get("details"):
            st.caption(rustfs_status.get("details", ""))

    with col2:
        pg_status = storage.get("postgres_size", {})
        st.metric("📏 Kích thước PostgreSQL", pg_status.get("size", "N/A"))

    st.markdown("---")

    # Documents section
    st.markdown("#### 📄 Thống kê tài liệu")

    documents = health_data.get("documents", {})
    total_docs = documents.get("total", 0)
    active_docs = documents.get("active", 0)
    failed_docs = documents.get("failed", 0)
    processing_docs = documents.get("processing", 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tổng số", total_docs)
    with col2:
        st.metric("Đang hoạt động", active_docs)
    with col3:
        st.metric("Đang xử lý", processing_docs)
    with col4:
        st.metric("Thất bại", failed_docs)

    st.markdown("---")

    # Worker section
    st.markdown("#### ⚙️ Worker Celery")

    worker = health_data.get("worker", {})
    worker_status = worker.get("status", "unknown")
    worker_emoji = "✅" if worker_status == "healthy" else "❌"
    st.metric(f"{worker_emoji} Trạng thái", worker_status.upper())

    if worker.get("details"):
        st.caption(worker.get("details", ""))

    st.markdown("---")

    # Timestamp
    timestamp = health_data.get("timestamp", "")
    if timestamp:
        st.caption(f"Cập nhật lần cuối: {timestamp}")

else:
    st.error("Không thể lấy thông tin sức khỏe hệ thống.")

# Auto-refresh logic
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Manual refresh button
st.markdown("---")
if st.button("🔄 Làm mới ngay", use_container_width=True):
    st.rerun()
