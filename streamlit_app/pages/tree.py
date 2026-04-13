"""
Tree visualizer page for Streamlit app.
"""
import streamlit as st
from components.auth import check_authentication, logout
from components.api_client import api_client

# Configure page
st.set_page_config(
    page_title="Cây tài liệu",
    page_icon="🌳",
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

    # Navigation
    if st.button("💬 Chat", use_container_width=True):
        st.switch_page("pages/chat.py")

    if st.session_state.get('user_role') == 'admin':
        if st.button("📄 Tài liệu", use_container_width=True):
            st.switch_page("pages/documents.py")

    if st.button("🌳 Cây tài liệu", use_container_width=True):
        st.switch_page("pages/tree.py")

    if st.session_state.get('user_role') == 'admin':
        if st.button("🏥 Sức khỏe hệ thống", use_container_width=True):
            st.switch_page("pages/health.py")
        if st.button("👥 Quản lý người dùng", use_container_width=True):
            st.switch_page("pages/users.py")

    st.markdown("---")
    if st.button("🚪 Đăng xuất", use_container_width=True):
        logout()
        st.switch_page("pages/login.py")

# Main content
st.title("🌳 Cây phân cấp tài liệu")

# Document selection
st.markdown("---")
st.markdown("### 📄 Chọn tài liệu")

# Get available documents (admin only) or use selected document
if st.session_state.get('user_role') == 'admin':
    documents = api_client.get("/api/v1/documents")
    if documents:
        doc_options = {f"{doc.get('filename', 'Unknown')} ({doc.get('status', 'unknown')}): {doc.get('id')}": doc.get('id') for doc in documents}
        selected_doc = st.selectbox(
            "Chọn tài liệu để xem cấu trúc",
            options=list(doc_options.keys()),
            index=None,
            placeholder="-- Chọn tài liệu --"
        )
        if selected_doc:
            document_id = doc_options[selected_doc]
    else:
        st.info("Chưa có tài liệu nào.")
        st.stop()
else:
    # Non-admin users: need to have document_id passed from documents page
    document_id = st.session_state.get("selected_document_id")
    if not document_id:
        st.info("Vui lòng chọn tài liệu từ trang quản lý tài liệu.")
        st.stop()

# Search functionality
st.markdown("---")
st.markdown("### 🔍 Tìm kiếm")

search_query = st.text_input(
    "Tìm kiếm node theo tiêu đề hoặc nội dung",
    placeholder="Nhập từ khóa tìm kiếm...",
    key="tree_search"
)

# Display tree structure
if document_id:
    st.markdown("---")

    if search_query:
        # Search mode
        st.markdown("#### 📊 Kết quả tìm kiếm")
        response = api_client.get(
            f"/api/v1/tree/{document_id}/search",
            params={"query": search_query}
        )

        if response:
            results = response.get("results", [])
            if results:
                for i, result in enumerate(results, 1):
                    node_id = result.get("node_id")
                    title = result.get("title", "Unknown")
                    preview = result.get("preview", "")
                    highlight = result.get("highlight", "")

                    with st.expander(f"{i}. {title}", expanded=False):
                        st.markdown(f"**Node ID**: `{node_id}`")
                        st.markdown(f"**Preview**: {preview}")
                        st.markdown(f"**Highlight**: `{highlight}`")

                        # View details button
                        if st.button(f"🔍 Xem chi tiết", key=f"view_search_{node_id}"):
                            st.session_state.selected_node_id = node_id
                            st.rerun()
            else:
                st.info("Không tìm thấy kết quả nào.")
        else:
            st.error("Không thể tìm kiếm.")
    else:
        # Tree mode
        st.markdown("#### 📊 Cấu trúc phân cấp")
        response = api_client.get(f"/api/v1/tree/{document_id}")

        if response:
            document_title = response.get("document_title", "Unknown")
            total_nodes = response.get("total_nodes", 0)
            max_depth = response.get("max_depth", 0)
            nodes = response.get("nodes", [])

            st.info(f"📄 **Tài liệu**: {document_title} | **Số node**: {total_nodes} | **Độ sâu**: {max_depth}")

            if nodes:
                # Group nodes by level for better display
                nodes_by_level = {}
                for node in nodes:
                    level = node.get("level", 0)
                    if level not in nodes_by_level:
                        nodes_by_level[level] = []
                    nodes_by_level[level].append(node)

                # Display tree by level
                for level in sorted(nodes_by_level.keys()):
                    level_nodes = nodes_by_level[level]
                    level_label = {
                        0: "Tài liệu",
                        1: "Chương",
                        2: "Mục",
                        3: "Tiểu mục"
                    }.get(level, f"Cấp độ {level}")

                    st.markdown(f"##### {level_label}")

                    for node in level_nodes:
                        node_id = node.get("node_id")
                        title = node.get("title", "Unknown")
                        breadcrumb = node.get("breadcrumb", "")
                        child_count = node.get("child_count", 0)
                        text_length = node.get("text_length", 0)
                        page_number = node.get("page_number", "N/A")

                        # Display node as expandable
                        with st.expander(
                            f"{'📁' if child_count > 0 else '📄'} {title} "
                            f"({child_count} con, {text_length} ký tự, trang {page_number})",
                            expanded=False
                        ):
                            st.caption(f"**Breadcrumb**: {breadcrumb}")
                            st.caption(f"**Node ID**: `{node_id}`")
                            st.caption(f"**Số node con**: {child_count}")
                            st.caption(f"**Độ dài**: {text_length} ký tự")
                            st.caption(f"**Trang**: {page_number}")

                            # View details button
                            if st.button(f"🔍 Xem chi tiết", key=f"view_{node_id}"):
                                st.session_state.selected_node_id = node_id
                                st.rerun()
            else:
                st.info("Tài liệu chưa có cấu trúc phân cấp.")
        else:
            st.error("Không thể lấy cấu trúc tài liệu.")

# Display node details if selected
if st.session_state.get("selected_node_id"):
    st.markdown("---")
    st.markdown("#### 📝 Chi tiết node")

    node_id = st.session_state.selected_node_id
    response = api_client.get(f"/api/v1/tree/{document_id}/nodes/{node_id}")

    if response:
        title = response.get("title", "Unknown")
        level = response.get("level", 0)
        breadcrumb = response.get("breadcrumb", "")
        text = response.get("text", "")
        metadata = response.get("metadata", {})

        st.markdown(f"**Tiêu đề**: {title}")
        st.caption(f"**Cấp độ**: {level}")
        st.caption(f"**Breadcrumb**: {breadcrumb}")

        st.markdown("---")
        st.markdown("**Nội dung**:")
        st.markdown(text)

        st.markdown("---")
        st.markdown("**Metadata**:")
        st.json(metadata)

        if st.button("✅ Đóng", key="close_node"):
            st.session_state.selected_node_id = None
            st.rerun()
    else:
        st.error("Không thể lấy chi tiết node.")

# Footer
st.markdown("---")
st.caption("💡 Mẹo: Sử dụng thanh tìm kiếm để nhanh chóng tìm thấy nội dung bạn cần.")
