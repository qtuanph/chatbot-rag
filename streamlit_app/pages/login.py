"""Login page for Streamlit app."""

import streamlit as st
from components.auth import login

# Configure page
st.set_page_config(
    page_title="Đăng nhập",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Clear any existing session
if st.session_state.get("authenticated"):
    # Already logged in - redirect to app for role routing
    st.switch_page("app.py")


def show_login_page():
    """Display login page."""
    st.title("🔐 Đăng nhập")

    st.markdown("---")

    # Login form
    with st.form("login_form"):
        st.subheader("Thông tin đăng nhập")

        username = st.text_input(
            "Tên đăng nhập",
            placeholder="Nhập tên đăng nhập",
            max_chars=50
        )

        password = st.text_input(
            "Mật khẩu",
            type="password",
            placeholder="Nhập mật khẩu",
            max_chars=100
        )

        submit_button = st.form_submit_button("Đăng nhập", use_container_width=True)

        if submit_button:
            if not username or not password:
                st.error("Vui lòng nhập tên đăng nhập và mật khẩu.")
            else:
                with st.spinner("Đang đăng nhập..."):
                    if login(username, password):
                        st.success("Đăng nhập thành công!")
                        # Redirect to app.py for role-based routing
                        st.switch_page("app.py")
                    else:
                        st.error("Tên đăng nhập hoặc mật khẩu không đúng.")

    st.markdown("---")

    # Default credentials hint
    st.info("💡 **Tài khoản mặc định:**")
    col1, col2 = st.columns(2)
    with col1:
        st.text("**Admin**")
        st.code("admin / abc123")
    with col2:
        st.text("**Member**")
        st.code("member / abc123")


if __name__ == "__main__":
    show_login_page()
