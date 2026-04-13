"""
User management page for Streamlit app (admin only).
"""
import streamlit as st
from components.auth import check_authentication, check_admin_role, logout
from components.api_client import api_client

# Configure page
st.set_page_config(
    page_title="Quản lý người dùng",
    page_icon="👥",
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
                        type="secondary",
                        args=()
                    ):
                        if st.confirm(f"Bạn có chắc muốn xóa người dùng '{username}' không?"):
                            with st.spinner("Đang xóa..."):
                                # Note: API doesn't have delete user endpoint yet
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
