import logging
import time
import httpx
import asyncio

from app.adapters.base import BaseParser, IngestedNode, ParsedNodeType, ParsingMetadata
from app.core.config import settings
from app.core.file_formats import extract_file_format

logger = logging.getLogger(__name__)

LLAMA_CLOUD_API_BASE = "https://api.cloud.llamaindex.ai/api/parsing"


class LlamaParseParser(BaseParser):
    """
    Cloud-based LlamaParse API implementation.
    Replaces local Docling to save local GPU/CPU resources.
    """

    async def parse(
        self,
        filename: str,
        content: bytes,
        document_id: str | None = None,
    ) -> tuple[list[IngestedNode], ParsingMetadata]:
        start_time = time.time()
        source_format = extract_file_format(filename)
        doc_id = document_id or filename

        logger.info("Uploading %s to LlamaParse Cloud...", filename)

        async with httpx.AsyncClient(timeout=120.0) as client:
            # 1. Upload the file
            headers = {
                "Authorization": f"Bearer {settings.llama_cloud_api_key}",
                "Accept": "application/json",
            }
            files = {"file": (filename, content, "application/pdf")}
            data = {
                "language": "vi",
                "premium_mode": "true",
                "parsing_instruction": "STRICT RULE: You MUST format ALL numbered section titles (e.g., '4. ', '4.1 ', '5.2.1 ') as proper Markdown headings using '#', '##', '###' respectively. Do not merge sections. Maintain exact hierarchical markdown structure for all chapters and subsections.",
            }
            upload_res = await client.post(f"{LLAMA_CLOUD_API_BASE}/upload", headers=headers, files=files, data=data)
            upload_res.raise_for_status()
            job_id = upload_res.json()["id"]

            logger.info("LlamaParse job started: %s. Polling for completion...", job_id)

            # 2. Poll for completion
            while True:
                status_res = await client.get(f"{LLAMA_CLOUD_API_BASE}/job/{job_id}", headers=headers)
                status_res.raise_for_status()
                status_data = status_res.json()
                status = status_data.get("status")

                if status == "SUCCESS":
                    logger.info("LlamaParse job %s SUCCESS.", job_id)
                    break
                elif status == "ERROR":
                    raise Exception(f"LlamaParse error: {status_data}")

                await asyncio.sleep(2)

            # 3. Retrieve markdown result
            md_res = await client.get(f"{LLAMA_CLOUD_API_BASE}/job/{job_id}/result/markdown", headers=headers)
            md_res.raise_for_status()
            markdown_content = md_res.json()["markdown"]

        logger.info("LlamaParse extraction complete. Chunking markdown...")

        # We will use Docling's markdown section extractor logic (re-used here for compatibility)
        # to split the markdown into chunks and sections
        nodes, sections_data, ok = self._extract_sections_from_markdown(markdown_content, doc_id, source_format)

        quality_score = 1.0 if ok and nodes else 0.0

        metadata = ParsingMetadata(
            engine_used="llamaparse",
            source_format=source_format,
            docling_used=False,
            fallback_used=False,
            quality_score=quality_score,
            parse_time_ms=(time.time() - start_time) * 1000,
            node_count=len(nodes),
            total_text_chars=sum(len(n.text) for n in nodes),
            sections_data=self._refine_sections(sections_data),
            raw_md_content=markdown_content,
        )

        return self._refine_nodes(nodes), metadata

    def _extract_sections_from_markdown(
        self, markdown_text: str, document_id: str, source_format: str
    ) -> tuple[list[IngestedNode], list[dict], bool]:
        """Parse markdown into sections and split into chunks."""
        nodes, sections_data = self.parse_from_markdown(markdown_text, document_id, source_format)
        return nodes, sections_data, True

    @staticmethod
    def parse_from_markdown(
        markdown_text: str, document_id: str, source_format: str = "markdown"
    ) -> tuple[list[IngestedNode], list[dict]]:
        """Parse markdown text into IngestedNodes and sections without calling LlamaParse API.

        Reuses the same local parsing logic (MarkdownNodeParser + SentenceSplitter)
        that runs after the LlamaParse API returns markdown.
        """
        import uuid
        from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
        from llama_index.core import Document
        from llama_index.core.schema import TextNode

        chunk_size_tokens = settings.retrieval_chunk_size
        chunk_overlap_tokens = settings.retrieval_chunk_overlap

        llama_doc = Document(text=markdown_text)
        md_parser = MarkdownNodeParser()
        base_nodes = md_parser.get_nodes_from_documents([llama_doc])

        merged_nodes: list[tuple[str, str, list[str]]] = []
        for node in base_nodes:
            hp = node.metadata.get("Header_Path") or node.metadata.get("header_path")
            if isinstance(hp, str):
                hp_list = [h.strip() for h in hp.split("/") if h.strip()]
            else:
                hp_list = hp or []
            title = hp_list[-1] if hp_list else ""

            text = node.get_content().strip()
            if not text:
                continue

            if merged_nodes and merged_nodes[-1][1] == title:
                merged_nodes[-1] = (merged_nodes[-1][0] + "\n" + text, title, hp_list)
            else:
                merged_nodes.append((text, title, hp_list))

        if not merged_nodes:
            merged_nodes.append(("", "Untitled", ["Untitled"]))

        splitter = SentenceSplitter(
            chunk_size=chunk_size_tokens,
            chunk_overlap=chunk_overlap_tokens,
            include_metadata=False,
        )

        nodes = []
        sections_data = []
        global_order = 0

        for idx, (content, title, header_path) in enumerate(merged_nodes):
            if not header_path:
                header_path = [f"Phần {idx + 1}"]

            level = len(header_path)
            section_id = f"sec_{idx:04d}"

            merged_node = TextNode(text=content)
            merged_node.metadata["Header_Path"] = "/".join(header_path)

            chunk_nodes = splitter.get_nodes_from_documents([merged_node])

            sections_data.append(
                {
                    "section_id": section_id,
                    "parent_section_id": None,
                    "title": title,
                    "content": content,
                    "section_type": "section",
                    "level": level,
                    "order_index": idx,
                    "page_range": "1",
                    "image_count": 0,
                    "table_count": 0,
                    "chunk_count": len(chunk_nodes),
                    "breadcrumb": header_path,
                    "metadata": {},
                }
            )

            for chunk in chunk_nodes:
                nodes.append(
                    IngestedNode(
                        node_id=str(uuid.uuid4()),
                        document_id=document_id,
                        text=chunk.get_content(),
                        node_type=ParsedNodeType.PARAGRAPH,
                        page_number=1,
                        section_title=title,
                        parent_id=None,
                        order=global_order,
                        metadata={
                            "source_format": source_format,
                            "section_id": section_id,
                            "section_level": level,
                            "breadcrumb": header_path,
                        },
                    )
                )
                global_order += 1

        return nodes, sections_data

    def _refine_nodes(self, nodes: list[IngestedNode]) -> list[IngestedNode]:
        for node in nodes:
            node.text = node.text.replace("\u0000", "").strip()
        return [n for n in nodes if n.text]

    def _refine_sections(self, sections: list[dict]) -> list[dict]:
        for sec in sections:
            if sec.get("content"):
                sec["content"] = sec["content"].replace("\u0000", "").strip()
        return sections
