"""Chat page for RAG interaction."""

import streamlit as st
from components.auth import check_authentication, logout
from components.api_client import api_client

# Configure page
st.set_page_config(
    page_title="Chat với Tài liệu",
    page_icon="💬",
    layout="wide"
)

# Check authentication
if not check_authentication():
    st.stop()

# Sidebar
with st.sidebar:
    st.title(f"👤 {st.session_state.get('username', 'User')}")
    st.caption(f"Vai trò: {st.session_state.get('user_role', 'member').title()}")

    st.markdown("---")

    # Admin can access dashboard
    if st.session_state.get('user_role') == 'admin':
        if st.button("👑 Admin Dashboard", use_container_width=True):
            st.switch_page("pages/admin.py")
        st.markdown("---")

    # Logout button
    if st.button("🚪 Đăng xuất", use_container_width=True):
        logout()
        st.switch_page("pages/login.py")

# Main content
st.title("💬 Chat với Tài liệu")

st.markdown("---")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Chat container
chat_container = st.container()

with chat_container:
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Show citations if available
            if message.get("citations"):
                with st.expander("📚 Nguồn tham khảo"):
                    for i, citation in enumerate(message["citations"], 1):
                        st.markdown(f"**{i}.** {citation}")

# Chat input
if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
    # Add user message to history
    st.session_state.chat_history.append({
        "role": "user",
        "content": prompt
    })

    # Display user message
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)

    # Get AI response
    with chat_container:
        with st.chat_message("assistant"):
            with st.spinner("Đang xử lý..."):
                response = api_client.post(
                    "/api/v1/chat",
                    data={"query": prompt}
                )

            if response:
                answer = response.get("answer", "Xin lỗi, không có phản hồi.")
                citations = response.get("citations", [])

                st.markdown(answer)

                # Show citations if available
                if citations:
                    with st.expander("📚 Nguồn tham khảo"):
                        for i, citation in enumerate(citations, 1):
                            st.markdown(f"**{i}.** {citation}")

                # Add assistant response to history
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer,
                    "citations": citations
                })
            else:
                st.error("Không thể nhận phản hồi từ server.")

# Sidebar - Clear chat
with st.sidebar:
    st.markdown("---")
    if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
        st.session_state.chat_history = []
        st.success("Đã xóa lịch sử chat!")
        st.rerun()
