"""
Streamlit Tree Visualizer for hierarchical document exploration.

Features:
- Hierarchical tree display (top-to-bottom)
- Click node → view header + full context
- Zoom/pan for large documents
- Color coding by depth level
- Search functionality
"""

import os
import requests
import streamlit as st
from typing import Dict, List, Optional

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
API_V1_PREFIX = os.getenv("API_V1_PREFIX", "/api/v1")
FULL_API_URL = f"{API_BASE_URL}{API_V1_PREFIX}"

# Page config
st.set_page_config(
    page_title="Document Tree Visualizer",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for tree styling
st.markdown("""
<style>
    .tree-container {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .node-header {
        font-weight: bold;
        font-size: 1.1em;
        padding: 8px;
        margin: 4px 0;
        border-radius: 4px;
        cursor: pointer;
    }
    .node-content {
        padding: 12px;
        margin: 8px 0;
        background-color: #f0f2f6;
        border-radius: 6px;
        border-left: 4px solid #1f77b4;
        white-space: pre-wrap;
        word-wrap: break-word;
        max-height: 400px;
        overflow-y: auto;
    }
    .breadcrumb {
        color: #666;
        font-size: 0.9em;
        margin-bottom: 8px;
    }
    .metadata {
        background-color: #e8ecf1;
        padding: 8px;
        border-radius: 4px;
        margin-top: 8px;
        font-size: 0.85em;
    }
    .level-1 { background-color: #d4edda; }
    .level-2 { background-color: #d1ecf1; }
    .level-3 { background-color: #fff3cd; }
    .level-4 { background-color: #f8d7da; }
    .level-5 { background-color: #e2d3f0; }
    .level-6 { background-color: #fce4ec; }
</style>
""", unsafe_allow_html=True)


class TreeVisualizer:
    """Tree visualizer main application."""

    def __init__(self):
        self.session = requests.Session()
        self.current_document_id = None
        self.tree_data = None
        self.nodes_map = {}

    def fetch_document_tree(self, document_id: str) -> Optional[Dict]:
        """Fetch tree structure from API."""
        try:
            response = self.session.get(
                f"{FULL_API_URL}/tree/{document_id}",
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Failed to fetch tree: {response.status_code}")
                return None
        except Exception as e:
            st.error(f"Error fetching tree: {str(e)}")
            return None

    def fetch_node_details(self, document_id: str, node_id: str) -> Optional[Dict]:
        """Fetch node details from API."""
        try:
            response = self.session.get(
                f"{FULL_API_URL}/tree/{document_id}/nodes/{node_id}",
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Failed to fetch node: {response.status_code}")
                return None
        except Exception as e:
            st.error(f"Error fetching node: {str(e)}")
            return None

    def search_nodes(self, document_id: str, query: str) -> List[Dict]:
        """Search nodes by query."""
        try:
            response = self.session.get(
                f"{FULL_API_URL}/tree/{document_id}/search",
                params={"query": query},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("results", [])
            else:
                st.error(f"Search failed: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Error searching: {str(e)}")
            return []

    def build_tree_structure(self, nodes: List[Dict]) -> List[Dict]:
        """Build hierarchical tree from flat node list."""
        # Create node map
        for node in nodes:
            self.nodes_map[node["node_id"]] = {
                **node,
                "children": []
            }

        # Build tree
        root_nodes = []
        for node in nodes:
            node_id = node["node_id"]
            parent_id = node.get("parent_id")

            if parent_id and parent_id in self.nodes_map:
                self.nodes_map[parent_id]["children"].append(self.nodes_map[node_id])
            else:
                root_nodes.append(self.nodes_map[node_id])

        return root_nodes

    def render_node(self, node: Dict, level: int = 0, indent: int = 0):
        """Render a single node with expand/collapse."""
        node_id = node["node_id"]
        title = node["title"]
        node_level = node["level"]
        child_count = node["child_count"]

        # Create unique key for expand/collapse
        expand_key = f"expand_{node_id}"

        # Level-based color coding
        level_class = f"level-{min(node_level, 6)}"

        # Indentation
        indentation = "&nbsp;" * (indent * 4)

        # Node header
        with st.container():
            col1, col2, col3 = st.columns([1, 6, 1])

            with col1:
                if child_count > 0:
                    if st.button("📂", key=f"btn_{node_id}", help="Toggle children"):
                        if expand_key in st.session_state:
                            del st.session_state[expand_key]
                        else:
                            st.session_state[expand_key] = True

            with col2:
                # Clickable node title
                if st.button(
                    f"{indentation}{title}",
                    key=f"node_{node_id}",
                    help=f"Level {node_level} • {child_count} children • {node['text_length']} chars"
                ):
                    st.session_state[f"selected_{node_id}"] = True

            with col3:
                st.caption(f"L{node_level}")

        # Show full content if selected
        if st.session_state.get(f"selected_{node_id}"):
            with st.container():
                node_details = self.fetch_node_details(self.current_document_id, node_id)
                if node_details:
                    st.markdown(f"<div class='breadcrumb'>📍 {node_details['breadcrumb']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='node-content'>", unsafe_allow_html=True)
                    st.markdown(f"**{node_details['title']}**\n\n")
                    st.text(node_details['text'])
                    st.markdown("</div>", unsafe_allow_html=True)

                    # Metadata
                    with st.expander("📊 Metadata"):
                        st.json(node_details['metadata'])

        # Render children if expanded
        if expand_key in st.session_state and node.get("children"):
            for child in node["children"]:
                self.render_node(child, level + 1, indent + 1)

    def render_tree(self):
        """Render the complete tree."""
        if not self.tree_data or not self.tree_data.get("nodes"):
            st.info("📭 No nodes found for this document")
            return

        # Document info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Nodes", self.tree_data["total_nodes"])
        with col2:
            st.metric("Max Depth", self.tree_data["max_depth"])
        with col3:
            st.caption(f"Document: {self.tree_data['document_title']}")

        st.markdown("---")

        # Build and render tree
        nodes = self.tree_data["nodes"]
        tree = self.build_tree_structure(nodes)

        st.markdown("### 🌳 Document Structure")
        st.markdown("Click any node to view full content. Use 📂 to expand/collapse sections.")

        with st.container():
            for root_node in tree:
                self.render_node(root_node)

    def render_search(self):
        """Render search interface."""
        st.markdown("### 🔍 Search Nodes")

        query = st.text_input(
            "Search in titles and content...",
            placeholder="Enter keywords to search...",
            key="search_query"
        )

        if query and len(query) >= 2:
            results = self.search_nodes(self.current_document_id, query)

            if results:
                st.success(f"Found {len(results)} results")

                for idx, result in enumerate(results):
                    node_id = result["node_id"]
                    title = result["title"]
                    preview = result["preview"]
                    highlight = result["highlight"]

                    with st.expander(f"📄 {title}", expanded=False):
                        st.markdown(f"<div class='node-content'>", unsafe_allow_html=True)
                        st.markdown(f"**Match:** '{highlight}'\n\n")
                        st.text(preview)
                        st.markdown("</div>", unsafe_allow_html=True)

                        # Button to view full node
                        if st.button(f"View Full Node", key=f"search_view_{node_id}"):
                            st.session_state[f"selected_{node_id}"] = True
                            st.rerun()
            else:
                st.info("No results found")

    def run(self):
        """Main application."""
        st.title("🌳 Document Tree Visualizer")
        st.markdown("Explore hierarchical document structure with interactive tree view")

        # Sidebar
        with st.sidebar:
            st.header("⚙️ Settings")

            # Document selection
            document_id = st.text_input(
                "Document ID",
                placeholder="Enter UUID...",
                help="Enter the document ID to visualize"
            )

            st.markdown("---")
            st.markdown("### Instructions")
            st.markdown("""
            1. Enter Document ID (UUID)
            2. Click **Load Tree**
            3. Click node title to view content
            4. Use 📂 to expand/collapse
            5. Use Search tab to find text
            """)

            st.markdown("---")
            st.markdown("### Legend")
            st.markdown("""
            - 📂 = Expand/Collapse
            - L1, L2... = Level depth
            - Color = Depth level
            """)

        # Main area tabs
        if document_id:
            self.current_document_id = document_id

            tab1, tab2 = st.tabs(["🌳 Tree View", "🔍 Search"])

            with tab1:
                if st.button("🔄 Load Tree", key="load_tree_btn"):
                    with st.spinner("Loading tree structure..."):
                        self.tree_data = self.fetch_document_tree(document_id)

                if self.tree_data:
                    self.render_tree()
                elif "tree_data" not in st.session_state:
                    st.info("👈 Click 'Load Tree' to view document structure")

            with tab2:
                if self.tree_data:
                    self.render_search()
                else:
                    st.info("👈 Load tree first, then search")
        else:
            st.info("👈 Enter Document ID in sidebar to begin")


def main():
    """Entry point."""
    app = TreeVisualizer()
    app.run()


if __name__ == "__main__":
    main()
