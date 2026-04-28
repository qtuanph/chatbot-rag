"""Repository for ChatSession and ChatMessage data access."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession


class ChatRepository:
    """Data access layer for ChatSession and ChatMessage models."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ── ChatSession ──────────────────────────────────────────────────

    def get_session(self, session_id: str) -> dict | None:
        row = self.session.get(ChatSession, session_id)
        return self._session_to_dict(row) if row else None

    def create_session(self, *, session_id: str, user_id: str, title: str = "Active chat") -> dict:
        chat_session = ChatSession(id=session_id, user_id=user_id, title=title)
        self.session.add(chat_session)
        self.session.commit()
        self.session.refresh(chat_session)
        return self._session_to_dict(chat_session)

    def update_session_title(self, session_id: str, title: str) -> None:
        chat_session = self.session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.title = title
            self.session.commit()

    def touch_session(self, session_id: str) -> None:
        chat_session = self.session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.updated_at = func.now()
            self.session.commit()

    def list_sessions_with_counts(self, user_id: str) -> list[dict]:
        rows = (
            self.session.query(
                ChatSession.id,
                ChatSession.title,
                ChatSession.created_at,
                ChatSession.updated_at,
                func.count(ChatMessage.id).label("message_count"),
            )
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.user_id == user_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )
        return [
            {
                "session_id": str(r.id),
                "title": r.title or "Chat session",
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "message_count": r.message_count,
            }
            for r in rows
        ]

    # ── ChatMessage ──────────────────────────────────────────────────

    def count_messages(self, session_id: str) -> int:
        return self.session.query(func.count(ChatMessage.id)).filter(ChatMessage.session_id == session_id).scalar() or 0

    def list_messages(self, session_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        rows = (
            self.session.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._message_to_dict(m) for m in rows]

    def get_messages_for_history(self, session_id: str) -> list[dict]:
        """Get all messages for a session, returned as role/content dicts for Redis hydration."""
        rows = (
            self.session.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in rows]

    def create_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
        model_used: str | None = None,
    ) -> dict:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations or [],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            model_used=model_used,
        )
        self.session.add(msg)
        # Touch session updated_at so sidebar ordering reflects activity
        chat_session = self.session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.updated_at = func.now()
        self.session.commit()
        self.session.refresh(msg)
        return self._message_to_dict(msg)

    def save_user_message(self, session_id: str, content: str) -> None:
        """Save a user message and touch the session."""
        self.session.add(ChatMessage(session_id=session_id, role="user", content=content))
        chat_session = self.session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.updated_at = func.now()
        self.session.commit()

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _session_to_dict(s: ChatSession) -> dict:
        return {
            "id": str(s.id),
            "user_id": str(s.user_id) if s.user_id else None,
            "title": s.title,
            "deleted_at": s.deleted_at.isoformat() if s.deleted_at else None,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }

    @staticmethod
    def _message_to_dict(m: ChatMessage) -> dict:
        return {
            "id": str(m.id),
            "session_id": str(m.session_id),
            "role": m.role,
            "content": m.content,
            "citations": m.citations or [],
            "model_used": m.model_used,
            "tokens_in": m.tokens_in,
            "tokens_out": m.tokens_out,
            "latency_ms": m.latency_ms,
            "created_at": m.created_at.isoformat(),
        }
