"""API client for communicating with backend."""

import os
import streamlit as st
import requests
from typing import Optional, Dict, Any


API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")


class APIClient:
    """Client for making authenticated API requests."""

    def __init__(self):
        """Initialize API client."""
        self.base_url = API_BASE_URL

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        token = st.session_state.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _handle_error(self, response: requests.Response) -> None:
        """
        Handle API error responses.

        Args:
            response: Response object
        """
        if response.status_code == 401:
            st.error("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.")
            st.session_state.authenticated = False
            st.session_state.token = None
            st.rerun()
        elif response.status_code == 403:
            st.error("Bạn không có quyền thực hiện thao tác này.")
        elif response.status_code == 404:
            st.error("Không tìm thấy tài nguyên.")
        elif response.status_code >= 500:
            st.error("Lỗi server. Vui lòng thử lại sau.")
        else:
            try:
                error_data = response.json()
                st.error(f"Lỗi: {error_data.get('detail', response.text)}")
            except:
                st.error(f"Lỗi: {response.text}")

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make GET request.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response JSON data or None if error
        """
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            self._handle_error(response)
            return None
        except requests.exceptions.Timeout:
            st.error("Yêu cầu hết thời gian chờ.")
            return None
        except requests.exceptions.ConnectionError:
            st.error("Không thể kết nối đến server.")
            return None
        except Exception as e:
            st.error(f"Lỗi kết nối: {str(e)}")
            return None

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
             files: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make POST request.

        Args:
            endpoint: API endpoint path
            data: Request body data
            files: Files to upload

        Returns:
            Response JSON data or None if error
        """
        try:
            headers = self._get_headers()
            # Remove Content-Type when uploading files
            if files:
                headers.pop("Content-Type", None)

            response = requests.post(
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=data,
                files=files,
                timeout=60
            )
            if response.status_code in [200, 201, 202]:
                return response.json()
            self._handle_error(response)
            return None
        except requests.exceptions.Timeout:
            st.error("Yêu cầu hết thời gian chờ.")
            return None
        except requests.exceptions.ConnectionError:
            st.error("Không thể kết nối đến server.")
            return None
        except Exception as e:
            st.error(f"Lỗi kết nối: {str(e)}")
            return None

    def delete(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Make DELETE request.

        Args:
            endpoint: API endpoint path

        Returns:
            Response JSON data or None if error
        """
        try:
            response = requests.delete(
                f"{self.base_url}{endpoint}",
                headers=self._get_headers(),
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            self._handle_error(response)
            return None
        except requests.exceptions.Timeout:
            st.error("Yêu cầu hết thời gian chờ.")
            return None
        except requests.exceptions.ConnectionError:
            st.error("Không thể kết nối đến server.")
            return None
        except Exception as e:
            st.error(f"Lỗi kết nối: {str(e)}")
            return None


# Global API client instance
api_client = APIClient()
