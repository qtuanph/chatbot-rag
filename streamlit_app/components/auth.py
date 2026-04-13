"""Authentication utilities for Streamlit app."""

import os
import streamlit as st
import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")


def login(username: str, password: str) -> bool:
    """
    Login to the backend API.

    Args:
        username: Username
        password: Password

    Returns:
        True if login successful, False otherwise
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.authenticated = True
            st.session_state.token = data.get("access_token")
            st.session_state.user_role = data.get("role", "member")
            st.session_state.username = username
            return True
        return False
    except Exception as e:
        st.error(f"Lỗi đăng nhập: {str(e)}")
        return False


def logout() -> bool:
    """
    Logout from the backend API.

    Returns:
        True if logout successful, False otherwise
    """
    try:
        if st.session_state.get("token"):
            response = requests.post(
                f"{API_BASE_URL}/api/v1/auth/logout",
                headers=get_auth_headers(),
                timeout=10
            )
            # Clear session state regardless of response
        st.session_state.authenticated = False
        st.session_state.token = None
        st.session_state.user_role = None
        st.session_state.username = None
        return True
    except Exception as e:
        st.error(f"Lỗi đăng xuất: {str(e)}")
        # Still clear session state on error
        st.session_state.authenticated = False
        st.session_state.token = None
        st.session_state.user_role = None
        st.session_state.username = None
        return False


def get_auth_headers() -> dict:
    """
    Get authentication headers for API requests.

    Returns:
        Dictionary with Authorization header
    """
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def check_authentication() -> bool:
    """
    Check if user is authenticated. Redirect to login if not.

    Returns:
        True if authenticated, False otherwise
    """
    if not st.session_state.get("authenticated", False):
        st.warning("Vui lòng đăng nhập để tiếp tục.")
        st.session_state.current_page = "Đăng nhập"
        st.rerun()
        return False
    return True


def check_admin_role() -> bool:
    """
    Check if current user has admin role.

    Returns:
        True if admin, False otherwise
    """
    return st.session_state.get("user_role") == "admin"
