"""Utility functions for RAG retrieval."""

from __future__ import annotations
from dataclasses import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.rag import RagContext, RagNode


def build_answer(query: str, context: RagContext) -> dict:
    """Build the answer seed from RAG context for AI provider."""
    if not context.nodes:
        return {
            "answer": (
                "Hiện tại tôi chưa có tài liệu nào để trả lời câu hỏi này. "
                "Vui lòng yêu cầu Admin upload thêm tài liệu vào hệ thống."
            ),
            "citations": [],
            "context": [],
        }

    section_map = {sec.section_id: sec for sec in (context.sections or [])}
    node_content_by_section: dict[str, list[RagNode]] = {}
    for node in context.nodes:
        if node.section_id:
            node_content_by_section.setdefault(node.section_id, []).append(node)
    sorted_nodes = sorted(context.nodes, key=lambda n: (n.document_id, n.section_id or "", n.score), reverse=True)

    context_blocks = []
    citations = []
    seen_sections: set[str] = set()
    citation_idx = 0

    for node in sorted_nodes:
        sec = section_map.get(node.section_id) if node.section_id else None

        if sec and sec.section_id not in seen_sections:
            seen_sections.add(sec.section_id)
            citation_idx += 1
            breadcrumb = " > ".join(sec.breadcrumb) if sec.breadcrumb else sec.title
            page = f" (trang {node.page_range})" if node.page_range else ""
            # Use full section content from the persisted section data (covers all chunks)
            sec_nodes = node_content_by_section.get(sec.section_id, [])
            full_sec_text = sec.content or "\n\n".join(
                n.full_text for n in sorted(sec_nodes, key=lambda x: x.score, reverse=True)
            )
            context_blocks.append(f"**{breadcrumb}** — {node.document_title}{page}\n{full_sec_text}")
            citations.append(
                {
                    "document_id": node.document_id,
                    "node_id": node.node_id,
                    "title": node.document_title,
                    "heading": node.heading,
                    "page_range": node.page_range,
                    "index": citation_idx,
                }
            )
        elif not sec:
            citation_idx += 1
            page = f" (trang {node.page_range})" if node.page_range else ""
            context_blocks.append(f"**{node.heading}** — {node.document_title}{page}\n{node.full_text}")
            citations.append(
                {
                    "document_id": node.document_id,
                    "node_id": node.node_id,
                    "title": node.document_title,
                    "heading": node.heading,
                    "page_range": node.page_range,
                    "index": citation_idx,
                }
            )

    context_text = "\n\n".join(context_blocks)
    answer = f"Câu hỏi: {query}\n\n" f"Tài liệu tham khảo:\n{context_text}"

    return {"answer": answer, "citations": citations, "context": [asdict(node) for node in sorted_nodes]}
