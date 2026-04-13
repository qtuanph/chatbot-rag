"""Documents management page."""

import streamlit as st
from components.auth import check_authentication, check_admin_role
from components.api_client import api_client


def show_documents_page():
    """Display documents management page."""
    if not check_authentication():
        return

    st.title("📄 Quản lý Tài liệu")

    st.markdown("---")

    # Load documents list
    with st.spinner("Đang tải danh sách tài liệu..."):
        documents = api_client.get("/api/v1/documents")

    if not documents:
        st.error("Không thể tải danh sách tài liệu.")
        return

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

    # Admin: Upload section
    if check_admin_role():
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
                    # Admin: Delete button
                    if check_admin_role():
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
