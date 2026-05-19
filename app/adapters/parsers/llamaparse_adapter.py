import logging
import time
import httpx
import asyncio

from app.adapters.base import BaseParser, IngestedNode, ParsedNodeType, ParsingMetadata
from app.adapters.parsers.markdown_cleaner import MarkdownCleaner
from app.core.config import settings
from app.core.file_formats import extract_file_format

logger = logging.getLogger(__name__)

LLAMA_CLOUD_API_BASE = settings.llama_cloud_api_base


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

        # Text/markdown: skip LlamaParse API, parse directly
        if source_format in ("markdown", "text"):
            markdown_text = content.decode("utf-8")
            cleaned = MarkdownCleaner().clean(markdown_text)
            nodes, sections_data = self.parse_from_markdown(cleaned, doc_id, source_format)
            ok = True
            engine_used = "local"
            raw_md = markdown_text
        else:
            logger.info("Uploading %s to LlamaParse Cloud...", filename)

            async with httpx.AsyncClient(timeout=settings.llama_cloud_timeout) as client:
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
                upload_res = await client.post(
                    f"{LLAMA_CLOUD_API_BASE}/upload", headers=headers, files=files, data=data
                )
                upload_res.raise_for_status()
                job_id = upload_res.json()["id"]

                logger.info("LlamaParse job started: %s. Polling for completion...", job_id)

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

                md_res = await client.get(f"{LLAMA_CLOUD_API_BASE}/job/{job_id}/result/markdown", headers=headers)
                md_res.raise_for_status()
                markdown_content = md_res.json()["markdown"]

            logger.info("LlamaParse extraction complete. Chunking markdown...")

            nodes, sections_data, ok = self._extract_sections_from_markdown(markdown_content, doc_id, source_format)
            engine_used = "llamaparse"
            raw_md = markdown_content

        quality_score = 1.0 if ok and nodes else 0.0

        metadata = ParsingMetadata(
            engine_used=engine_used,
            source_format=source_format,
            docling_used=False,
            fallback_used=False,
            quality_score=quality_score,
            parse_time_ms=(time.time() - start_time) * 1000,
            node_count=len(nodes),
            total_text_chars=sum(len(n.text) for n in nodes),
            sections_data=self._refine_sections(sections_data),
            raw_md_content=raw_md,
        )

        return self._refine_nodes(nodes), metadata

    def _extract_sections_from_markdown(
        self, markdown_text: str, document_id: str, source_format: str
    ) -> tuple[list[IngestedNode], list[dict], bool]:
        """Parse markdown into sections and split into chunks."""
        cleaned = MarkdownCleaner().clean(markdown_text)
        nodes, sections_data = self.parse_from_markdown(cleaned, document_id, source_format)
        return nodes, sections_data, True

    @staticmethod
    def parse_from_markdown(
        markdown_text: str, document_id: str, source_format: str = "markdown"
    ) -> tuple[list[IngestedNode], list[dict]]:
        """Parse markdown text into IngestedNodes and sections without calling LlamaParse API.

        Returns ONE IngestedNode per markdown section (by heading).
        Downstream LlamaIngestionPipeline handles SentenceSplitter chunking.
        """
        import uuid
        from llama_index.core.node_parser import MarkdownNodeParser
        from llama_index.core import Document

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

        # Min-chunk guard: merge tiny sections with the next section
        min_chars = settings.ingestion_min_section_chars
        guarded: list[tuple[str, str, list[str]]] = []
        for item in merged_nodes:
            if guarded and len(item[0]) < min_chars:
                prev_content, prev_title, prev_hp = guarded[-1]
                guarded[-1] = (prev_content + "\n" + item[0], prev_title, prev_hp)
            else:
                guarded.append(item)
        merged_nodes = guarded

        nodes = []
        sections_data = []

        for idx, (content, title, header_path) in enumerate(merged_nodes):
            if not header_path:
                header_path = [f"Phần {idx + 1}"]

            level = len(header_path)
            section_id = f"sec_{idx:04d}"

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
                    "chunk_count": 1,
                    "breadcrumb": header_path,
                    "metadata": {},
                }
            )

            nodes.append(
                IngestedNode(
                    node_id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=content,
                    node_type=ParsedNodeType.PARAGRAPH,
                    page_number=1,
                    section_title=title,
                    parent_id=None,
                    order=idx,
                    metadata={
                        "source_format": source_format,
                        "section_id": section_id,
                        "section_level": level,
                        "breadcrumb": header_path,
                    },
                )
            )

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
