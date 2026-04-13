"""Main entry point for Streamlit RAG chatbot application - Role-based routing."""

import streamlit as st
from components.auth import check_admin_role

# Page configuration
st.set_page_config(
    page_title="RAG Chatbot - Vietnamese Enterprise Documents",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "username" not in st.session_state:
    st.session_state.username = None


def main():
    """Main application entry point with role-based routing."""

    # Route to login if not authenticated
    if not st.session_state.authenticated:
        st.switch_page("pages/login.py")

    # Authenticated - route based on role
    if check_admin_role():
        # Admin dashboard
        st.switch_page("pages/admin.py")
    else:
        # Member - chat interface
        st.switch_page("pages/chat.py")


if __name__ == "__main__":
    main()
