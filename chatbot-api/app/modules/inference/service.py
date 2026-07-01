from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from llama_index.core import Settings
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.evaluation import FaithfulnessEvaluator
from llama_index.core.response_synthesizers import ResponseMode, get_response_synthesizer
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.llms.openai_like import OpenAILike

from app.core.config import settings
from app.modules.chat.retrieval.pipeline import retrieve_context
from app.modules.chat.retrieval.usage_tracker import track_usage
from app.modules.chat.utils.query_normalizer import normalize_query, ALL_DEFAULT_STOPWORDS
from app.modules.chat.utils.chat_utils import compute_cost, is_greeting
from app.models.rag import RagContext, RagNode
from app.modules.documents.repositories.section_repository import SectionRepository
from app.modules.tenants.repository import TenantRepository

logger = logging.getLogger("uvicorn.error")


@dataclass
class CompletionResult:
    content: str
    citations: list[dict[str, Any]]
    usage: dict[str, Any]
    model: str


def _to_llama_role(role: str) -> MessageRole:
    mapping = {
        "system": MessageRole.SYSTEM,
        "user": MessageRole.USER,
        "assistant": MessageRole.ASSISTANT,
        "tool": MessageRole.TOOL,
    }
    return mapping.get(role.lower(), MessageRole.USER)


class PublicInferenceService:
    def __init__(
        self, tenant_repo: TenantRepository, section_repo: SectionRepository, semantic_cache: Any = None
    ) -> None:
        self.tenant_repo = tenant_repo
        self.section_repo = section_repo
        self.semantic_cache = semantic_cache

    async def complete(
        self,
        *,
        tenant_id: str,
        messages: list[dict[str, str]],
        thinking_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: str | None = None,
    ) -> CompletionResult:
        user_query = self._latest_user_query(messages)
        query_vector = None
        normalized_query = None
        if self.semantic_cache and user_query:
            normalized_query = normalize_query(user_query, stopwords=ALL_DEFAULT_STOPWORDS)
            embed_model = Settings.embed_model
            query_vector = await embed_model.aget_query_embedding(normalized_query)
            cached = await self.semantic_cache.get(tenant_id, query_vector)
            if cached:
                usage = cached.get("usage", {})
                usage["cached"] = True
                return CompletionResult(
                    content=cached["content"], citations=cached["citations"], usage=usage, model=cached["model"]
                )

        setting = await self._get_tenant_setting(tenant_id)
        context = await self._resolve_context(
            tenant_id=tenant_id,
            messages=messages,
            user_id=user_id,
        )
        llm_messages = self._build_messages(messages, setting, context)
        llm = Settings.llm
        previous_temperature = getattr(llm, "temperature", None)
        previous_max_tokens = getattr(llm, "max_tokens", None)
        if temperature is not None:
            llm.temperature = temperature
        if max_tokens is not None:
            llm.max_tokens = max_tokens
        t0 = time.perf_counter()
        try:
            response = await llm.achat(llm_messages)
        finally:
            if temperature is not None:
                llm.temperature = previous_temperature
            if max_tokens is not None:
                llm.max_tokens = previous_max_tokens
        
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = getattr(response, "additional_kwargs", {}) or {}
        usage["latency_ms"] = latency_ms
        content = ""
        message = getattr(response, "message", None)
        if message is not None and hasattr(message, "content"):
            content = str(message.content or "")
        if not content and hasattr(response, "text"):
            content = str(response.text or "")
        content = await self._ensure_grounded_answer(user_query=user_query, answer=content.strip(), context=context)
        result = CompletionResult(
            content=content,
            citations=self._build_citations(context),
            usage=self._normalize_usage(usage),
            model=getattr(llm, "model", settings.ai_proxy_default_model or "chatbot-rag"),
        )
        if self.semantic_cache and normalized_query and query_vector:
            await self.semantic_cache.set(
                tenant_id,
                normalized_query,
                query_vector,
                {
                    "content": result.content,
                    "citations": result.citations,
                    "usage": result.usage,
                    "model": result.model,
                },
            )
        provider = type("UsageProxy", (), {"last_usage": result.usage, "model_name": result.model})()
        track_usage(provider, endpoint="public.chat.completions", tenant_id=tenant_id)
        return result

    async def stream_complete(
        self,
        *,
        tenant_id: str,
        messages: list[dict[str, str]],
        thinking_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        user_query = self._latest_user_query(messages)
        query_vector = None
        normalized_query = None
        if self.semantic_cache and user_query:
            normalized_query = normalize_query(user_query, stopwords=ALL_DEFAULT_STOPWORDS)
            embed_model = Settings.embed_model
            query_vector = await embed_model.aget_query_embedding(normalized_query)
            cached = await self.semantic_cache.get(tenant_id, query_vector)
            if cached:
                created = int(time.time())
                completion_id = f"chatcmpl-{created}"
                model_name = cached["model"]

                # Yield content block
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created, 'model': model_name, 'choices': [{'index': 0, 'delta': {'content': cached['content']}, 'finish_reason': None}]})}\n\n"

                # Yield citations & stats
                usage = cached.get("usage", {})
                usage["cached"] = True
                yield f"data: {json.dumps({'done': True, 'citations': cached['citations'], 'stats': usage | {'model': model_name}})}\n\n"
                return

        setting = await self._get_tenant_setting(tenant_id)
        context = await self._resolve_context(
            tenant_id=tenant_id,
            messages=messages,
            user_id=user_id,
        )
        llm_messages = self._build_messages(messages, setting, context)
        llm = Settings.llm
        previous_temperature = getattr(llm, "temperature", None)
        previous_max_tokens = getattr(llm, "max_tokens", None)
        if temperature is not None:
            llm.temperature = temperature
        if max_tokens is not None:
            llm.max_tokens = max_tokens

        created = int(time.time())
        model_name = getattr(llm, "model", settings.ai_proxy_default_model or "chatbot-rag")
        completion_id = f"chatcmpl-{created}"
        usage_info: dict[str, Any] = {}
        collected_text = ""
        user_query = self._latest_user_query(messages)
        try:
            t0 = time.perf_counter()
            if thinking_mode:
                yield f"data: {json.dumps({'thinking': True, 'done': False})}\n\n"
            response = await llm.astream_chat(llm_messages)
            async for chunk in response:
                delta = chunk.delta if hasattr(chunk, "delta") else str(chunk)
                if delta:
                    collected_text += delta
                    payload = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                if hasattr(chunk, "additional_kwargs") and isinstance(chunk.additional_kwargs, dict):
                    usage_info.update(chunk.additional_kwargs)
        finally:
            if temperature is not None:
                llm.temperature = previous_temperature
            if max_tokens is not None:
                llm.max_tokens = previous_max_tokens
            usage_info["latency_ms"] = (time.perf_counter() - t0) * 1000

        final_text = collected_text.strip()
        if final_text:
            grounded_text = await self._ensure_grounded_answer(
                user_query=user_query,
                answer=final_text,
                context=context,
            )
            if grounded_text != final_text:
                self._emit_debug(
                    "RAG_STREAM_GUARD",
                    query=user_query,
                    decision="post-stream-mismatch",
                    original_preview=self._preview_text(final_text),
                    grounded_preview=self._preview_text(grounded_text),
                )

        result = CompletionResult(
            content=grounded_text,
            citations=self._build_citations(context),
            usage=self._normalize_usage(usage_info),
            model=model_name,
        )
        if self.semantic_cache and normalized_query and query_vector:
            await self.semantic_cache.set(
                tenant_id,
                normalized_query,
                query_vector,
                {
                    "content": result.content,
                    "citations": result.citations,
                    "usage": result.usage,
                    "model": result.model,
                },
            )
        provider = type("UsageProxy", (), {"last_usage": result.usage, "model_name": result.model})()
        track_usage(provider, endpoint="public.chat.stream", tenant_id=tenant_id)
        yield f"data: {json.dumps({'done': True, 'citations': result.citations, 'stats': result.usage | {'model': result.model}})}\n\n"

        if thinking_mode:
            yield f"data: {json.dumps({'thinking': False, 'done': False})}\n\n"
        final_payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "citations": result.citations,
            "usage": result.usage,
        }
        yield f"data: {json.dumps(final_payload)}\n\n"
        yield "data: [DONE]\n\n"

    async def _get_tenant_setting(self, tenant_id: str) -> dict[str, Any]:
        tenant = await self.tenant_repo.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found")
        setting = await self.tenant_repo.get_setting(tenant_id)
        if setting is None:
            return {
                "chatbot_display_name": tenant["name"],
                "welcome_message": "Xin chào, tôi có thể hỗ trợ gì cho bạn?",
                "system_instruction": "",
            }
        return setting

    @staticmethod
    def _latest_user_query(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user" and message.get("content", "").strip():
                return message["content"].strip()
        raise ValueError("At least one user message is required")

    @staticmethod
    def _build_retrieval_queries(messages: list[dict[str, str]]) -> list[str]:
        user_messages = [
            message.get("content", "").strip()
            for message in messages
            if message.get("role") == "user" and message.get("content", "").strip()
        ]
        if not user_messages:
            raise ValueError("At least one user message is required")

        history_count = max(0, min(settings.retrieval_history_query_count, len(user_messages) - 1))
        if history_count == 0:
            return [user_messages[-1]]

        queries: list[str] = [user_messages[-1]]
        for previous in user_messages[-history_count - 1 : -1]:
            if previous and previous not in queries:
                queries.append(previous)
        return queries[: history_count + 1]

    async def _resolve_context(
        self,
        *,
        tenant_id: str,
        messages: list[dict[str, str]],
        user_id: str | None,
    ) -> RagContext:
        user_query = self._latest_user_query(messages)
        if is_greeting(user_query):
            self._emit_debug("RAG_BYPASS", tenant_id=tenant_id, query=user_query, reason="greeting")
            return RagContext(nodes=[], sections=None, confidence={"node_count": 0, "bypass_reason": "greeting"})

        try:
            context = await retrieve_context(
                self._build_retrieval_queries(messages),
                limit=settings.retrieval_rerank_top_k,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return await self._hydrate_context(context)
        except Exception as e:
            self._emit_debug("RAG_RETRIEVAL_ERROR", error=str(e), tenant_id=tenant_id)
            from app.models.rag import RagNode
            error_node = RagNode(
                node_id="sys_error",
                parent_id=None,
                document_id="sys",
                document_title="System Status",
                heading="Missing Documents",
                summary="System has no documents.",
                full_text="[SYSTEM INSTRUCTION] Hiện tại hệ thống chưa có tài liệu nào, hoặc dữ liệu đang được khởi tạo. Bạn hãy phản hồi một cách lịch sự, yêu cầu người dùng upload thêm tài liệu vào hệ thống để bạn có thể hỗ trợ họ nhé.",
                page_range=None,
                section_id=None,
                section_code=None,
                breadcrumb=tuple(),
                node_kind="system",
                score=1.0,
            )
            return RagContext(nodes=[error_node], sections=None, confidence={"node_count": 1, "error": str(e)})

    async def _hydrate_context(self, context: RagContext) -> RagContext:
        if not settings.retrieval_section_hydration_enabled or not context.nodes:
            return context

        target_nodes = [node for node in context.nodes[: settings.retrieval_section_hydration_top_k] if node.section_id]
        section_doc_pairs = [
            (node.document_id, node.section_id) for node in target_nodes if node.document_id and node.section_id
        ]
        if not section_doc_pairs:
            return context

        section_rows = await self.section_repo.get_sections_for_rag(section_doc_pairs)
        section_map = {
            (str(row.get("document_id") or ""), str(row.get("section_id") or "")): row for row in section_rows
        }

        hydrated_nodes: list[RagNode] = []
        for node in context.nodes:
            key = (node.document_id, node.section_id or "")
            section = section_map.get(key)
            if not section:
                hydrated_nodes.append(node)
                continue
            full_text = str(section.get("content") or node.full_text or "").strip() or node.full_text
            heading = str(section.get("title") or node.heading or "").strip() or node.heading
            page_range = section.get("page_range") or node.page_range
            hydrated_nodes.append(
                RagNode(
                    node_id=node.node_id,
                    parent_id=node.parent_id,
                    document_id=node.document_id,
                    document_title=node.document_title,
                    heading=heading,
                    summary=full_text[:400],
                    full_text=full_text,
                    page_range=str(page_range) if page_range else None,
                    section_id=node.section_id,
                    section_code=node.section_code,
                    breadcrumb=node.breadcrumb,
                    node_kind=node.node_kind,
                    score=node.score,
                )
            )
        return RagContext(nodes=hydrated_nodes, sections=context.sections, confidence=context.confidence)

    @staticmethod
    def _preview_text(text: str, limit: int = 240) -> str:
        normalized = " ".join(str(text or "").split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit]}..."

    def _context_debug_payload(self, context: RagContext, limit: int = 5) -> list[dict[str, Any]]:
        return [
            {
                "node_id": node.node_id,
                "score": round(float(node.score or 0.0), 6),
                "document_id": node.document_id,
                "document_title": node.document_title,
                "section_id": node.section_id,
                "heading": node.heading,
                "page_range": node.page_range,
                "preview": self._preview_text(node.full_text or node.summary or ""),
            }
            for node in context.nodes[:limit]
        ]

    @staticmethod
    def _emit_debug(event: str, **payload: Any) -> None:
        message = json.dumps({"event": event, **payload}, ensure_ascii=False)
        logger.info(message)
        print(message, flush=True)

    def _build_messages(self, messages: list[dict[str, str]], setting: dict[str, Any], context) -> list[ChatMessage]:
        context_blocks = []
        for idx, node in enumerate(context.nodes[:8], start=1):
            title = node.document_title or "Document"
            heading = node.heading or "Relevant section"
            section_code = f" [{node.section_code}]" if node.section_code else ""
            page = f" (page {node.page_range})" if node.page_range else ""
            breadcrumb = " > ".join(node.breadcrumb or ())
            breadcrumb_line = f"\nĐường dẫn: {breadcrumb}" if breadcrumb else ""
            context_blocks.append(
                f"[Nguồn {idx}] {title} - {heading}{section_code}{page}{breadcrumb_line}\n{node.full_text}"
            )

        system_prompt = (
            "Bạn là trợ lý doanh nghiệp hoạt động trong đúng phạm vi tenant hiện tại. "
            "Chỉ được trả lời dựa trên tài liệu của tenant và ngữ cảnh hội thoại được cung cấp. "
            "Nếu thông tin chưa đủ, hãy nói rõ là chưa đủ và không được bịa nội dung."
        )
        tenant_instruction = (setting.get("system_instruction") or "").strip()
        if tenant_instruction:
            system_prompt += f"\n\nInstruction riêng của tenant:\n{tenant_instruction}"
        if context_blocks:
            system_prompt += "\n\nNgữ cảnh truy xuất:\n" + "\n\n".join(context_blocks[:10])
        system_prompt += (
            "\n\nQUY TẮC BẮT BUỘC:"
            "\n- Không được bịa menu, nút, báo cáo, mã trạng thái, trường dữ liệu hoặc quy trình."
            "\n- Chỉ được nêu tên chức năng, đường dẫn menu, bước thao tác khi chúng xuất hiện rõ trong ngữ cảnh truy xuất."
            "\n- Nếu tài liệu không xác nhận đủ, phải trả lời là chưa đủ căn cứ để hướng dẫn chi tiết."
            "\n- Với câu hỏi thao tác phần mềm, ưu tiên trả lời ngắn, đúng, bám sát tài liệu; không suy diễn từ kinh nghiệm chung."
        )

        llm_messages = [ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)]
        recent_messages = messages[-settings.ai_max_history_messages :]
        for message in recent_messages:
            llm_messages.append(
                ChatMessage(role=_to_llama_role(message["role"]), content=message.get("content", "").strip())
            )
        self._emit_debug(
            "RAG_PROMPT",
            tenant_instruction=bool(tenant_instruction),
            context_nodes=len(context.nodes),
            recent_messages=len(recent_messages),
            context=self._context_debug_payload(context),
        )
        return llm_messages

    @staticmethod
    def _build_citations(context) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for idx, node in enumerate(context.nodes, start=1):
            citations.append(
                {
                    "index": idx,
                    "document_id": node.document_id,
                    "title": node.document_title,
                    "heading": node.heading,
                    "section_code": node.section_code,
                    "breadcrumb": list(node.breadcrumb or ()),
                    "page_range": node.page_range,
                    "node_id": node.node_id,
                }
            )
        return citations

    @staticmethod
    def _normalize_usage(usage: dict[str, Any]) -> dict[str, Any]:
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        latency_ms = float(usage.get("latency_ms", 0.0) or 0.0)
        result = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
        }
        result.update(compute_cost(prompt_tokens, completion_tokens))
        return result

    def _build_insufficient_evidence_answer(self, context: RagContext) -> str:
        headings = []
        for node in context.nodes[:4]:
            heading = (node.heading or "").strip()
            if heading and heading not in headings:
                headings.append(heading)
        if headings:
            joined = "; ".join(headings)
            return (
                "Tài liệu truy xuất hiện chưa đủ căn cứ để mình hướng dẫn thao tác chi tiết mà không suy diễn. "
                f"Mình chỉ xác nhận được các mục liên quan sau: {joined}. "
                "Bạn hãy hỏi theo đúng tên chức năng hoặc mục trong phần mềm để mình trả lời bám sát tài liệu hơn."
            )
        return (
            "Tài liệu truy xuất hiện chưa đủ căn cứ để mình hướng dẫn thao tác chi tiết mà không suy diễn. "
            "Bạn hãy nêu rõ tên chức năng, phân hệ hoặc mục màn hình cần làm để mình trả lời đúng theo tài liệu."
        )

    async def _ensure_grounded_answer(self, *, user_query: str, answer: str, context: RagContext) -> str:
        if not answer.strip():
            return answer.strip()
        confidence = context.confidence or {}
        if confidence.get("bypass_reason") == "greeting":
            self._emit_debug("RAG_GROUNDING", query=user_query, decision="bypass-greeting")
            return answer.strip()

        contexts = [
            "\n".join(part for part in [node.document_title, node.heading, node.full_text] if part).strip()
            for node in context.nodes
            if (node.full_text or "").strip() or (node.heading or "").strip()
        ]
        if not contexts:
            self._emit_debug("RAG_GROUNDING", query=user_query, decision="no-context", fallback="insufficient-evidence")
            return self._build_insufficient_evidence_answer(context)

        if not self._should_run_grounding_verification(context):
            self._emit_debug(
                "RAG_GROUNDING",
                query=user_query,
                decision="skip-verification",
                confidence=context.confidence or {},
            )
            return answer.strip()

        evaluation = await self._evaluate_faithfulness(
            user_query=user_query,
            answer=answer.strip(),
            contexts=contexts,
        )
        if evaluation is None:
            self._emit_debug("RAG_GROUNDING", query=user_query, decision="evaluator-unavailable", keep="original")
            return answer.strip()

        if self._is_faithful(evaluation):
            self._emit_debug(
                "RAG_GROUNDING",
                query=user_query,
                decision="faithful",
                score=getattr(evaluation, "score", None),
                passing=getattr(evaluation, "passing", None),
            )
            return answer.strip()

        self._emit_debug(
            "RAG_GROUNDING",
            query=user_query,
            decision="repair-needed",
            score=getattr(evaluation, "score", None),
            passing=getattr(evaluation, "passing", None),
            answer_preview=self._preview_text(answer),
        )
        repaired_answer = await self._synthesize_grounded_answer(user_query=user_query, context=context)
        if repaired_answer:
            repaired_evaluation = await self._evaluate_faithfulness(
                user_query=user_query,
                answer=repaired_answer,
                contexts=contexts,
            )
            if repaired_evaluation is None or self._is_faithful(repaired_evaluation):
                self._emit_debug(
                    "RAG_GROUNDING",
                    query=user_query,
                    decision="repair-succeeded",
                    repaired_preview=self._preview_text(repaired_answer),
                    repaired_score=(
                        getattr(repaired_evaluation, "score", None) if repaired_evaluation is not None else None
                    ),
                    repaired_passing=(
                        getattr(repaired_evaluation, "passing", None) if repaired_evaluation is not None else None
                    ),
                )
                return repaired_answer
            self._emit_debug(
                "RAG_GROUNDING",
                query=user_query,
                decision="repair-failed",
                repaired_preview=self._preview_text(repaired_answer),
                repaired_score=getattr(repaired_evaluation, "score", None),
                repaired_passing=getattr(repaired_evaluation, "passing", None),
            )

        self._emit_debug("RAG_GROUNDING", query=user_query, decision="fallback-insufficient-evidence")
        return self._build_insufficient_evidence_answer(context)

    @staticmethod
    def _should_run_grounding_verification(context: RagContext) -> bool:
        confidence = context.confidence or {}
        node_count = int(confidence.get("node_count", len(context.nodes)) or len(context.nodes))
        top_score = float(confidence.get("top_score", 0.0) or 0.0)
        dominance_ratio = float(confidence.get("dominance_ratio", 0.0) or 0.0)
        unique_document_count = int(confidence.get("unique_document_count", 0) or 0)

        if node_count == 0:
            return True
        if (
            node_count <= 2
            and unique_document_count <= 1
            and top_score > 0
            and dominance_ratio >= settings.retrieval_rerank_skip_dominance_ratio
        ):
            return False
        return True

    async def _evaluate_faithfulness(
        self,
        *,
        user_query: str,
        answer: str,
        contexts: list[str],
    ) -> Any | None:
        try:
            evaluator_llm = Settings.llm
            if settings.ai_evaluation_model:
                evaluator_llm = OpenAILike(
                    model=settings.ai_evaluation_model,
                    api_base=f"{settings.ai_proxy_url}/v1",
                    api_key=settings.ai_proxy_api_key or "no-key",
                    is_chat_model=True,
                    temperature=0.0,
                    context_window=128000,
                    max_tokens=settings.ai_max_output_tokens,
                    timeout=settings.ai_proxy_timeout,
                )
            evaluator = FaithfulnessEvaluator(llm=evaluator_llm, raise_error=False)
            return await evaluator.aevaluate(
                query=user_query,
                response=answer,
                contexts=contexts,
            )
        except Exception:
            return None

    @staticmethod
    def _is_faithful(evaluation: Any) -> bool:
        if getattr(evaluation, "invalid_result", False):
            return False
        if getattr(evaluation, "passing", None) is False:
            return False
        score = getattr(evaluation, "score", None)
        if score is not None and float(score) <= 0:
            return False
        return True

    async def _synthesize_grounded_answer(self, *, user_query: str, context: RagContext) -> str | None:
        nodes = self._to_source_nodes(context)
        if not nodes:
            return None

        try:
            synthesizer = get_response_synthesizer(
                llm=Settings.llm,
                response_mode=ResponseMode.REFINE,
                structured_answer_filtering=True,
                use_async=True,
            )
            response = await synthesizer.asynthesize(
                query=user_query,
                nodes=nodes,
            )
        except Exception:
            logger.warning("RAG_SYNTHESIZE query=%r failed", user_query, exc_info=True)
            return None

        response_text = getattr(response, "response", None) or getattr(response, "response_txt", None) or str(response)
        cleaned = str(response_text or "").strip()
        self._emit_debug(
            "RAG_SYNTHESIZE",
            query=user_query,
            nodes=len(nodes),
            response_preview=self._preview_text(cleaned),
        )
        return cleaned or None

    @staticmethod
    def _to_source_nodes(context: RagContext) -> list[NodeWithScore]:
        source_nodes: list[NodeWithScore] = []
        for node in context.nodes:
            text = str(node.full_text or "").strip()
            if not text:
                continue
            text_node = TextNode(
                id_=node.node_id,
                text=text,
                metadata={
                    "document_id": node.document_id,
                    "document_title": node.document_title,
                    "heading": node.heading,
                    "section_id": node.section_id,
                    "page_range": node.page_range,
                },
            )
            source_nodes.append(NodeWithScore(node=text_node, score=float(node.score or 0.0)))
        return source_nodes
