import asyncio
import logging
import re
import time
from dataclasses import dataclass

import httpx

from app.adapters.base import BaseParser, IngestedNode, ParsedNodeType, ParsingMetadata
from app.adapters.parsers.markdown_cleaner import MarkdownCleaner
from app.core.config import settings
from app.core.file_formats import extract_file_format

logger = logging.getLogger(__name__)

LLAMA_CLOUD_API_BASE = settings.llama_cloud_api_base
HEADING_RE = re.compile(r"^(#{1,6})\s+(?P<title>.+?)\s*$")
SECTION_CODE_RE = re.compile(r"^(?P<code>\d+(?:\.\d+)*)(?:[\)\.:]|(?=\s)|$)")


@dataclass(slots=True)
class _HeadingState:
    level: int
    title: str
    section_id: str


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
                    "parsing_instruction": (
                        "STRICT RULE: You MUST format ALL numbered section titles "
                        "(e.g., '4. ', '4.1 ', '5.2.1 ') as proper Markdown headings "
                        "using '#', '##', '###' respectively. Do not merge sections. "
                        "Maintain exact hierarchical markdown structure for all chapters and subsections."
                    ),
                }
                upload_res = await client.post(
                    f"{LLAMA_CLOUD_API_BASE}/upload",
                    headers=headers,
                    files=files,
                    data=data,
                )
                upload_res.raise_for_status()
                job_id = upload_res.json()["id"]

                logger.info("LlamaParse job started: %s. Polling for completion...", job_id)

                max_polls = int(settings.llama_cloud_timeout // 2)
                polls = 0
                while True:
                    status_res = await client.get(f"{LLAMA_CLOUD_API_BASE}/job/{job_id}", headers=headers)
                    status_res.raise_for_status()
                    status_data = status_res.json()
                    status = status_data.get("status")

                    if status == "SUCCESS":
                        logger.info("LlamaParse job %s SUCCESS.", job_id)
                        break
                    if status == "ERROR":
                        raise Exception(f"LlamaParse error: {status_data}")

                    polls += 1
                    if polls >= max_polls:
                        raise TimeoutError(
                            f"LlamaParse job {job_id} timed out after {settings.llama_cloud_timeout} seconds"
                        )

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
        cleaned = MarkdownCleaner().clean(markdown_text)
        nodes, sections_data = self.parse_from_markdown(cleaned, document_id, source_format)
        return nodes, sections_data, True

    @staticmethod
    def parse_from_markdown(
        markdown_text: str, document_id: str, source_format: str = "markdown"
    ) -> tuple[list[IngestedNode], list[dict]]:
        import uuid

        lines = markdown_text.splitlines()
        stack: list[_HeadingState] = []
        current_heading: _HeadingState | None = None
        current_content: list[str] = []
        sections_data: list[dict] = []
        nodes: list[IngestedNode] = []
        section_counter = 0
        preface_buffer: list[str] = []

        def build_section_id(title: str, index: int) -> str:
            code = LlamaParseParser._extract_section_code(title)
            if code:
                return f"sec-{code.replace('.', '-')}-{index:04d}"
            return f"sec-{index:04d}"

        def flush_current() -> None:
            nonlocal current_heading, current_content, section_counter
            if current_heading is None:
                return

            content = "\n".join(current_content).strip()
            if not content:
                current_heading = None
                current_content = []
                return

            section_id = current_heading.section_id
            parent_section_id = None
            if len(stack) >= 2 and stack[-1].section_id == section_id:
                parent_section_id = stack[-2].section_id

            breadcrumb = [item.title for item in stack if item.section_id != section_id]
            breadcrumb.append(current_heading.title)
            section_code = LlamaParseParser._extract_section_code(current_heading.title)
            breadcrumb_text = " > ".join(breadcrumb)

            sections_data.append(
                {
                    "section_id": section_id,
                    "parent_section_id": parent_section_id,
                    "section_code": section_code,
                    "title": current_heading.title,
                    "content": content,
                    "section_type": "section",
                    "level": current_heading.level,
                    "order_index": section_counter,
                    "page_range": "1",
                    "image_count": 0,
                    "table_count": 0,
                    "chunk_count": 0,
                    "breadcrumb": breadcrumb,
                    "breadcrumb_text": breadcrumb_text,
                    "artifact_metadata": {},
                }
            )

            nodes.append(
                IngestedNode(
                    node_id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=content,
                    node_type=ParsedNodeType.SECTION,
                    page_number=1,
                    section_title=current_heading.title,
                    parent_id=parent_section_id,
                    order=section_counter,
                    metadata={
                        "source_format": source_format,
                        "section_id": section_id,
                        "section_code": section_code,
                        "section_level": current_heading.level,
                        "breadcrumb": breadcrumb,
                        "breadcrumb_text": breadcrumb_text,
                    },
                )
            )

            section_counter += 1
            current_heading = None
            current_content = []

        for raw_line in lines:
            match = HEADING_RE.match(raw_line.strip())
            if match:
                if current_heading is None and preface_buffer:
                    preface_title = "Giới thiệu"
                    current_heading = _HeadingState(
                        level=1,
                        title=preface_title,
                        section_id=build_section_id(preface_title, section_counter),
                    )
                    stack = [current_heading]
                    current_content = preface_buffer[:]
                    preface_buffer = []
                    flush_current()
                    stack = []

                flush_current()
                level = len(match.group(1))
                title = match.group("title").strip()
                while stack and stack[-1].level >= level:
                    stack.pop()
                heading = _HeadingState(level=level, title=title, section_id=build_section_id(title, section_counter))
                stack.append(heading)
                current_heading = heading
                current_content = []
                continue

            if current_heading is None:
                if raw_line.strip():
                    preface_buffer.append(raw_line)
                continue
            current_content.append(raw_line)

        if current_heading is None and preface_buffer:
            preface_title = "Giới thiệu"
            current_heading = _HeadingState(
                level=1,
                title=preface_title,
                section_id=build_section_id(preface_title, section_counter),
            )
            stack = [current_heading]
            current_content = preface_buffer[:]

        flush_current()

        if not sections_data:
            fallback_title = "Nội dung"
            fallback_section_id = build_section_id(fallback_title, 0)
            fallback_breadcrumb = [fallback_title]
            fallback_text = markdown_text.strip()
            sections_data.append(
                {
                    "section_id": fallback_section_id,
                    "parent_section_id": None,
                    "section_code": None,
                    "title": fallback_title,
                    "content": fallback_text,
                    "section_type": "section",
                    "level": 1,
                    "order_index": 0,
                    "page_range": "1",
                    "image_count": 0,
                    "table_count": 0,
                    "chunk_count": 0,
                    "breadcrumb": fallback_breadcrumb,
                    "breadcrumb_text": fallback_title,
                    "artifact_metadata": {},
                }
            )
            nodes.append(
                IngestedNode(
                    node_id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=fallback_text,
                    node_type=ParsedNodeType.SECTION,
                    page_number=1,
                    section_title=fallback_title,
                    parent_id=None,
                    order=0,
                    metadata={
                        "source_format": source_format,
                        "section_id": fallback_section_id,
                        "section_code": None,
                        "section_level": 1,
                        "breadcrumb": fallback_breadcrumb,
                        "breadcrumb_text": fallback_title,
                    },
                )
            )

        return nodes, sections_data

    @staticmethod
    def _extract_section_code(title: str) -> str | None:
        match = SECTION_CODE_RE.match(str(title or "").strip())
        if not match:
            return None
        return match.group("code")

    def _refine_nodes(self, nodes: list[IngestedNode]) -> list[IngestedNode]:
        for node in nodes:
            node.text = node.text.replace("\u0000", "").strip()
        return [n for n in nodes if n.text]

    def _refine_sections(self, sections: list[dict]) -> list[dict]:
        for sec in sections:
            if sec.get("content"):
                sec["content"] = sec["content"].replace("\u0000", "").strip()
        return sections
