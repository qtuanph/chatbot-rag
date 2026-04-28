"""Chat service — session management, context preparation, message persistence."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

import nh3

from app.core.config import settings
from app.repositories.chat_repository import ChatRepository
from app.utils.chat_store import ChatStore

logger = logging.getLogger(__name__)


class ChatService:
    """Business logic for chat sessions, context preparation, and message persistence."""

    def __init__(self, repo: ChatRepository, store: ChatStore, user_memory_service: Any = None) -> None:
        self.repo = repo
        self.store = store
        self._user_memory_service = user_memory_service

    # ── Full chat preparation ─────────────────────────────────────────

    async def prepare_chat(self, *, user_id: str, query: str, session_id: str | None = None) -> dict:
        """Prepare full chat context: validate → session → retrieval → answer seed.

        Returns dict with session_id, history, assistant_seed, citations, user_memories, scope_id.
        Raises ValueError on validation failure.
        """
        self.validate_query(query)

        scope_id = f"user:{user_id}"
        resolved_session_id = self.resolve_session(user_id=user_id, session_id=session_id)
        self.validate_session_id(resolved_session_id)

        self.get_or_create_session(session_id=resolved_session_id, user_id=user_id, query=query)
        history = self.store.get_history(scope_id, resolved_session_id)

        # Multi-query expansion
        queries = [query]
        if settings.retrieval_query_expansion_enabled:
            try:
                from app.services.retrieval.query_expand import expand_query

                queries = await asyncio.wait_for(expand_query(query), timeout=3.0)
                logger.info("[PERF] Query expansion: %d variants", len(queries))
            except Exception:
                logger.warning("Query expansion failed, using original query")

        # RAG retrieval
        context = await asyncio.to_thread(self.retrieve_rag_context, queries, 20)

        from app.services.retrieval.retrieval_service import build_answer

        assistant_seed = build_answer(query, context)
        raw_citations = assistant_seed.get("citations") or []
        citations = self.deduplicate_citations(raw_citations)

        # User memories
        user_memories = ""
        if self._user_memory_service:
            user_memories = self._user_memory_service.format_memories_for_prompt(user_id)

        return {
            "session_id": resolved_session_id,
            "scope_id": scope_id,
            "history": history,
            "assistant_seed": assistant_seed,
            "citations": citations,
            "user_memories": user_memories,
        }

    # ── RAG retrieval ────────────────────────────────────────────────

    @staticmethod
    def retrieve_rag_context(queries: list[str], limit: int = 20) -> Any:
        """Run RAG retrieval with a short-lived DB session. Returns RagContext."""
        from app.db.session import SessionLocal
        from app.services.retrieval.retrieval_service import retrieve_context

        with SessionLocal() as db_session:
            return retrieve_context(db_session, queries, limit)

    # ── Query validation ────────────────────────────────────────────

    @staticmethod
    def validate_query(query: str) -> None:
        """Validate and sanitize query input. Raises ValueError on failure."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        if len(query) > 5000:
            raise ValueError("Query too long (max 5000 characters)")
        sanitized = nh3.clean(query, tags=set(), attributes={})
        if sanitized != query:
            raise ValueError("Query contains invalid characters")

    # ── Session management ──────────────────────────────────────────

    def resolve_session(self, *, user_id: str, session_id: str | None) -> str:
        """Resolve or create a session ID. Returns session_id."""
        scope_id = f"user:{user_id}"
        resolved = session_id or self.store.get_active_session(scope_id) or str(uuid4())
        self.store.set_active_session(scope_id, resolved)
        return resolved

    @staticmethod
    def validate_session_id(session_id: str) -> None:
        """Validate UUID format of session ID. Raises ValueError."""
        try:
            UUID(session_id)
        except ValueError:
            raise ValueError("Invalid session ID format") from None

    def get_or_create_session(self, *, session_id: str, user_id: str, query: str) -> dict:
        """Get existing session or create new. Raises ValueError on ownership mismatch."""
        session = self.repo.get_session(session_id)

        if session is None:
            session = self.repo.create_session(session_id=session_id, user_id=user_id, title="Active chat")
        elif session.get("user_id") and str(session["user_id"]) != user_id:
            raise ValueError("Chat session does not belong to this user")

        if session.get("title") == "Active chat":
            new_title = query[:80] + ("..." if len(query) > 80 else "")
            self.repo.update_session_title(session_id, new_title)
            session["title"] = new_title

        scope_id = f"user:{user_id}"
        self.store.append_message(scope_id, session_id, "user", query)
        self.repo.save_user_message(session_id, query)

        if not self.store.history_exists(scope_id, session_id):
            db_msgs = self.repo.get_messages_for_history(session_id)
            self.store.hydrate_from_db(scope_id, session_id, db_msgs)

        return session

    # ── Message persistence ─────────────────────────────────────────

    def save_assistant_message(
        self,
        *,
        session_id: str,
        user_id: str,
        content: str,
        citations: list[dict] | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
        model_used: str | None = None,
    ) -> None:
        """Save assistant message to PostgreSQL + Redis."""
        try:
            self.repo.create_message(
                session_id=session_id,
                role="assistant",
                content=content,
                citations=citations,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                model_used=model_used,
            )
        except Exception as e:
            logger.error("Failed to save chat message: %s", e, exc_info=True)

        scope_id = f"user:{user_id}"
        self.store.append_message(scope_id, session_id, "assistant", content)

    # ── Memory extraction ────────────────────────────────────────────

    async def extract_memories(self, user_id: str, user_message: str, assistant_response: str) -> None:
        """Extract memories from conversation turn. Best-effort."""
        if not self._user_memory_service:
            return
        try:
            from app.adapters.ai import build_ai_provider

            provider = build_ai_provider()
            await self._user_memory_service.extract_memories_from_turn(
                user_id, user_message, assistant_response, provider
            )
        except Exception as e:
            logger.debug("Memory extraction failed (best-effort): %s", e)

    # ── Session listing ─────────────────────────────────────────────

    def create_session(self, *, user_id: str) -> dict:
        """Create a new empty chat session."""
        session_id = str(uuid4())
        session = self.repo.create_session(session_id=session_id, user_id=user_id, title="Active chat")
        return {
            "session_id": session["id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": 0,
        }

    def list_sessions(self, user_id: str) -> list[dict]:
        return self.repo.list_sessions_with_counts(user_id)

    # ── Message listing ─────────────────────────────────────────────

    def list_messages(self, *, session_id: str, user_id: str, limit: int = 20, offset: int = 0) -> dict:
        """List messages for a session. Raises ValueError if not found or ownership mismatch."""
        session = self.repo.get_session(session_id)
        if session is None:
            raise ValueError("Chat session not found")
        if session.get("user_id") and str(session["user_id"]) != user_id:
            raise ValueError("Chat session does not belong to this user")

        total = self.repo.count_messages(session_id)
        limit = max(1, min(limit, 100))

        effective_offset = max(0, total - offset - limit)
        effective_limit = min(limit, total - offset)

        if effective_limit <= 0:
            return {"messages": [], "total": total, "has_more": False}

        messages = self.repo.list_messages(session_id, offset=effective_offset, limit=effective_limit)
        has_more = effective_offset > 0

        return {
            "messages": [
                {
                    "id": m["id"],
                    "role": m["role"],
                    "content": m["content"],
                    "citations": m.get("citations") or [],
                    "created_at": m["created_at"],
                }
                for m in messages
            ],
            "total": total,
            "has_more": has_more,
        }

    # ── Utility methods ─────────────────────────────────────────────

    @staticmethod
    def compute_cost(tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * settings.ai_input_cost_per_1m + tokens_out * settings.ai_output_cost_per_1m) / 1_000_000

    @staticmethod
    def deduplicate_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group citations by document_id, merge page ranges into compact format."""
        if not citations:
            return []

        doc_groups: dict[str, list[dict]] = {}
        doc_titles: dict[str, str] = {}
        for citation in citations:
            doc_id = citation.get("document_id", "")
            if doc_id not in doc_groups:
                doc_groups[doc_id] = []
                doc_titles[doc_id] = citation.get("title", "Tài liệu")
            doc_groups[doc_id].append(citation)

        result = []
        for doc_id, cites in doc_groups.items():
            pages: set[int] = set()
            for c in cites:
                pr = c.get("page_range")
                if pr:
                    try:
                        parts = str(pr).split("-")
                        start = int(parts[0].strip())
                        end = int(parts[-1].strip())
                        pages.update(range(start, end + 1))
                    except (ValueError, IndexError):
                        pass

            page_display = ""
            if pages:
                sorted_pages = sorted(pages)
                ranges: list[str] = []
                range_start = sorted_pages[0]
                range_end = sorted_pages[0]
                for p in sorted_pages[1:]:
                    if p == range_end + 1:
                        range_end = p
                    else:
                        ranges.append(f"{range_start}" if range_start == range_end else f"{range_start}-{range_end}")
                        range_start = p
                        range_end = p
                ranges.append(f"{range_start}" if range_start == range_end else f"{range_start}-{range_end}")
                page_display = ", ".join(ranges)

            result.append(
                {
                    "document_id": doc_id,
                    "title": doc_titles.get(doc_id, "Tài liệu"),
                    "pages": page_display,
                }
            )

        return result

    @staticmethod
    def build_user_friendly_error(error: Exception) -> str:
        """Convert technical errors to user-friendly Vietnamese messages."""
        error_str = str(error).lower()
        if "timeout" in error_str or "timed out" in error_str:
            return "AI Model phản hồi quá chậm. Vui lòng thử câu hỏi ngắn hơn hoặc thử lại sau."
        elif "rate limit" in error_str or "429" in error_str:
            return "Đã đạt giới hạn request. Vui lòng chờ một chút rồi thử lại."
        elif "safety" in error_str or "blocked" in error_str:
            return "Nội dung không được phép. Vui lòng thử câu hỏi khác."
        elif "connection" in error_str:
            return "Lỗi kết nối với AI Model. Vui lòng kiểm tra mạng và thử lại."
        else:
            return "Lỗi không xác định. Vui lòng thử lại sau."
