"""Admin dashboard page with all admin functions."""

import streamlit as st
from components.auth import check_authentication, check_admin_role, logout
from components.api_client import api_client

# Configure page
st.set_page_config(
    page_title="Admin Dashboard",
    page_icon="👑",
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
    st.title("👑 Admin Dashboard")
    st.caption(f"Xin chào, {st.session_state.get('username', 'Admin')}")

    st.markdown("---")

    # Admin sections
    st.subheader("📊 Quản trị")

    section = st.radio(
        "Chọn mục:",
        ["📄 Tài liệu", "👥 Người dùng", "🏥 Sức khỏe hệ thống", "🌳 Cây tài liệu"],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Logout button
    if st.button("🚪 Đăng xuất", use_container_width=True):
        logout()
        st.switch_page("pages/login.py")

    # Chat link (for testing)
    st.markdown("---")
    st.caption("💡 Muốn chat?")
    if st.button("💬 Mở Chat", use_container_width=True):
        st.switch_page("pages/chat.py")

# Main content area
if section == "📄 Tài liệu":
    # Show documents page content
    st.title("📄 Quản lý Tài liệu")

    st.markdown("---")

    # Load documents list
    with st.spinner("Đang tải danh sách tài liệu..."):
        documents = api_client.get("/api/v1/documents")

    if not documents:
        st.error("Không thể tải danh sách tài liệu.")
        st.stop()

    docs_list = documents.get("documents", [])
    total_docs = documents.get("total", 0)

    # Statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tổng số", total_docs)
    with col2:
        processing = sum(1 for d in docs_list if d.get("status") == "processing")
        st.metric("Đang xử lý", processing)
    with col3:
        completed = sum(1 for d in docs_list if d.get("status") == "completed")
        st.metric("Hoàn thành", completed)
    with col4:
        failed = sum(1 for d in docs_list if d.get("status") == "failed")
        st.metric("Thất bại", failed)

    st.markdown("---")

    # Upload section
    st.subheader("📤 Tải lên tài liệu mới")

    with st.form("upload_form"):
        uploaded_file = st.file_uploader(
            "Chọn file PDF",
            type=["pdf"],
            help="Chỉ hỗ trợ file PDF"
        )

        submit_button = st.form_submit_button("Tải lên", use_container_width=True)

        if submit_button and uploaded_file:
            with st.spinner("Đang tải lên..."):
                # Prepare file for upload
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}

                response = api_client.post(
                    "/api/v1/upload",
                    files=files
                )

            if response:
                task_id = response.get("task_id")
                st.success(f"Đã tải lên thành công! Task ID: `{task_id}`")
                st.info("Đang xử lý tài liệu...")
                st.rerun()
            else:
                st.error("Không thể tải lên tài liệu.")

    st.markdown("---")

    # Documents list
    st.subheader("📋 Danh sách tài liệu")

    if not docs_list:
        st.info("Chưa có tài liệu nào.")
    else:
        for doc in docs_list:
            with st.expander(f"📄 {doc.get('filename', 'Unknown')} - {doc.get('status', '').upper()}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(f"**ID:** {doc.get('id')}")
                    st.write(f"**Trạng thái:** {doc.get('status')}")

                with col2:
                    st.write(f"**Ngày tải lên:** {doc.get('created_at', 'N/A')}")
                    st.write(f"**Kích thước:** {doc.get('file_size', 'N/A')} bytes")

                with col3:
                    # Delete button
                    if st.button(f"🗑️ Xóa", key=f"delete_{doc.get('id')}", use_container_width=True):
                        with st.spinner("Đang xóa..."):
                            response = api_client.delete(f"/api/v1/documents/{doc.get('id')}")

                        if response:
                            st.success("Đã xóa tài liệu!")
                            st.rerun()
                        else:
                            st.error("Không thể xóa tài liệu.")

                    # Show task status link
                    if doc.get("status") in ["pending", "processing"]:
                        if st.button(f"🔄 Kiểm tra trạng thái", key=f"status_{doc.get('id')}", use_container_width=True):
                            st.session_state.selected_task_id = doc.get("task_id")
                            st.rerun()

                # Show ingestion details
                if doc.get("ingestion_details"):
                    st.json(doc.get("ingestion_details"))

    # Selected task status
    if st.session_state.get("selected_task_id"):
        st.markdown("---")
        st.subheader("🔄 Trạng thái xử lý")

        task_id = st.session_state.selected_task_id
        with st.spinner("Đang kiểm tra trạng thái..."):
            status = api_client.get(f"/api/v1/status/{task_id}")

        if status:
            st.write(f"**Task ID:** {task_id}")
            st.write(f"**Trạng thái:** {status.get('status', 'N/A')}")
            st.write(f"**Tiến độ:** {status.get('progress', 0)}%")

            if status.get("error"):
                st.error(f"**Lỗi:** {status.get('error')}")
        else:
            st.error("Không thể kiểm tra trạng thái.")

        if st.button("Đóng", use_container_width=True):
            del st.session_state.selected_task_id
            st.rerun()

elif section == "👥 Người dùng":
    # Show user management page content
    st.title("👥 Quản lý người dùng")

    st.markdown("---")

    # Add user section
    st.markdown("### ➕ Thêm người dùng mới")

    with st.form("add_user_form"):
        new_username = st.text_input(
            "Tên đăng nhập",
            placeholder="Nhập tên đăng nhập",
            max_chars=50,
            help="Tên đăng nhập sẽ được chuyển thành chữ thường"
        )
        new_password = st.text_input(
            "Mật khẩu",
            type="password",
            placeholder="Nhập mật khẩu",
            max_chars=100,
            help="Mật khẩu phải có độ dài tối thiểu 6 ký tự"
        )
        new_role = st.selectbox(
            "Vai trò",
            options=["member", "admin"],
            help="Member: Chỉ chat, Admin: Quản lý tài liệu và người dùng"
        )

        submit_button = st.form_submit_button("Thêm người dùng", use_container_width=True)

        if submit_button:
            if not new_username or not new_password:
                st.error("Vui lòng nhập tên đăng nhập và mật khẩu.")
            elif len(new_password) < 6:
                st.error("Mật khẩu phải có độ dài tối thiểu 6 ký tự.")
            else:
                with st.spinner("Đang thêm người dùng..."):
                    response = api_client.post(
                        "/api/v1/auth/users",
                        data={
                            "username": new_username,
                            "password": new_password,
                            "role": new_role
                        }
                    )

                if response:
                    st.success(f"Đã thêm người dùng '{new_username}' thành công!")
                    st.rerun()
                else:
                    st.error("Không thể thêm người dùng.")

    st.markdown("---")

    # Users list section
    st.markdown("### 📋 Danh sách người dùng")

    # Fetch users
    with st.spinner("Đang tải danh sách người dùng..."):
        users = api_client.get("/api/v1/auth/users")

    if users:
        # Display users in a table
        for user in users:
            user_id = user.get("id")
            username = user.get("username", "Unknown")
            role = user.get("role", "member")

            # Role badge
            role_emoji = {
                "admin": "👑",
                "member": "👤"
            }.get(role, "❓")

            # User card
            with st.expander(f"{role_emoji} {username}", expanded=False):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.caption(f"**User ID**: `{user_id}`")
                with col2:
                    st.caption(f"**Vai trò**: {role.title()}")
                with col3:
                    # Prevent deleting self
                    is_self = username.lower() == st.session_state.get('username', '').lower()

                    if not is_self:
                        if st.button(
                            f"🗑️ Xóa",
                            key=f"delete_{user_id}",
                            type="secondary"
                        ):
                            st.warning("Tính năng xóa người dùng chưa được hỗ trợ.")
                    else:
                        st.caption("*(Không thể xóa chính mình)*")

        # Statistics
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            admin_count = sum(1 for u in users if u.get("role") == "admin")
            st.metric("👑 Admin", admin_count)
        with col2:
            member_count = sum(1 for u in users if u.get("role") == "member")
            st.metric("👤 Member", member_count)

    else:
        st.error("Không thể tải danh sách người dùng.")

    # Footer
    st.markdown("---")
    st.caption("💡 Mẹo: Tài khoản Admin có toàn quyền quản lý, tài khoản Member chỉ có thể chat.")

elif section == "🏥 Sức khỏe hệ thống":
    # Show health page content
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

    # Manual refresh button
    st.markdown("---")
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Làm mới ngay", use_container_width=True):
            st.rerun()
    with col2:
        if auto_refresh:
            import time
            time.sleep(30)
            st.rerun()

elif section == "🌳 Cây tài liệu":
    # Show tree viewer page content
    st.title("🌳 Xem Cây Tài liệu")

    st.markdown("---")

    # Document selection
    with st.spinner("Đang tải danh sách tài liệu..."):
        documents_response = api_client.get("/api/v1/documents")

    if not documents_response:
        st.error("Không thể tải danh sách tài liệu.")
        st.stop()

    docs_list = documents_response.get("documents", [])

    # Filter only completed documents
    completed_docs = [d for d in docs_list if d.get("status") == "completed"]

    if not completed_docs:
        st.warning("Chưa có tài liệu nào hoàn thành xử lý để hiển thị cây.")
        st.info("💡 Tải lên và chờ tài liệu xử lý xong để xem cấu trúc cây.")
    else:
        # Document selector
        doc_options = {f"{d.get('filename')} (ID: {d.get('id')}[:6]...)": d.get("id") for d in completed_docs}
        selected_doc_label = st.selectbox(
            "Chọn tài liệu để xem cây:",
            options=list(doc_options.keys())
        )

        if selected_doc_label:
            selected_doc_id = doc_options[selected_doc_label]

            # Display tree
            col1, col2 = st.columns([2, 1])

            with col1:
                st.subheader("📊 Cấu trúc phân cấp")

                # Fetch tree data
                with st.spinner("Đang tải cấu trúc cây..."):
                    tree_data = api_client.get(f"/api/v1/documents/{selected_doc_id}/tree")

                if tree_data:
                    # Display hierarchical tree
                    def render_tree(node, level=0):
                        """Recursively render tree nodes."""
                        indent = "│   " * level
                        prefix = "├── " if level > 0 else ""

                        # Node display
                        node_type = node.get("node_type", "unknown")
                        metadata = node.get("metadata", {})
                        header = metadata.get("header", f"Node {node.get('id', 'Unknown')[:8]}")

                        # Format display
                        type_emoji = {
                            "document": "📄",
                            "section": "📑",
                            "chunk": "📝"
                        }.get(node_type, "📌")

                        # Show node
                        st.markdown(f"{indent}{prefix}{type_emoji} **{header}**")
                        st.caption(f"{indent}│   ├── Type: {node_type}")
                        st.caption(f"{indent}│   ├── ID: {node.get('id', 'Unknown')[:8]}...")

                        # Show page range if available
                        if metadata.get("page_number"):
                            st.caption(f"{indent}│   └── Page: {metadata.get('page_number')}")

                        # Recursively render children
                        children = node.get("children", [])
                        if children:
                            for i, child in enumerate(children):
                                is_last = (i == len(children) - 1)
                                render_tree(child, level + 1)

                    # Render the tree
                    if tree_data.get("tree"):
                        render_tree(tree_data["tree"])
                    else:
                        st.warning("Không có dữ liệu cây.")
                else:
                    st.error("Không thể tải dữ liệu cây.")

            with col2:
                st.subheader("📋 Thông tin tài liệu")

                # Get document details
                doc_details = next((d for d in completed_docs if d.get("id") == selected_doc_id), None)

                if doc_details:
                    st.write(f"**📄 Tên file:** {doc_details.get('filename')}")
                    st.write(f"**📏 Kích thước:** {doc_details.get('file_size', 0):,} bytes")
                    st.write(f"**📅 Ngày tải lên:** {doc_details.get('created_at')}")
                    st.write(f"**✅ Trạng thái:** {doc_details.get('status').upper()}")

                    st.markdown("---")

                    # Ingestion details
                    if doc_details.get("ingestion_details"):
                        st.write("**🔧 Chi tiết xử lý:**")
                        st.json(doc_details.get("ingestion_details"))

                    st.markdown("---")

                    # Statistics
                    if tree_data and tree_data.get("stats"):
                        stats = tree_data["stats"]
                        st.write("**📊 Thống kê:**")
                        st.metric("Tổng nodes", stats.get("total_nodes", 0))
                        st.metric("Độ sâu max", stats.get("max_depth", 0))
                        st.metric("Số sections", stats.get("total_sections", 0))
                        st.metric("Số chunks", stats.get("total_chunks", 0))

    st.markdown("---")
    st.caption("💡 Cây tài liệu hiển thị cấu trúc phân cấp của tài liệu sau khi xử lý.")
