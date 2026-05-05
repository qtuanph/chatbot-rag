from datetime import datetime

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession


class ChatRepository:
    """Data access layer for ChatSession and ChatMessage models."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── ChatSession ──────────────────────────────────────────────────

    async def get_session(self, session_id: str) -> dict | None:
        row = await self.session.get(ChatSession, session_id)
        return self._session_to_dict(row) if row else None

    async def create_session(self, *, session_id: str, user_id: str, title: str = "Active chat") -> dict:
        chat_session = ChatSession(id=session_id, user_id=user_id, title=title)
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return self._session_to_dict(chat_session)

    async def update_session_title(self, session_id: str, title: str) -> None:
        stmt = update(ChatSession).where(ChatSession.id == session_id).values(title=title)
        await self.session.execute(stmt)
        await self.session.commit()

    async def touch_session(self, session_id: str) -> None:
        stmt = update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now())
        await self.session.execute(stmt)
        await self.session.commit()

    async def list_sessions_with_counts(self, user_id: str) -> list[dict]:
        stmt = (
            select(
                ChatSession.id,
                ChatSession.title,
                ChatSession.created_at,
                ChatSession.updated_at,
                func.count(ChatMessage.id).label("message_count"),
            )
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.user_id == user_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
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

    async def count_messages(self, session_id: str) -> int:
        stmt = select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_messages(self, session_id: str, offset: int = 0, limit: int = 100) -> list[dict]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._message_to_dict(m) for m in rows]

    async def get_messages_for_history(self, session_id: str) -> list[dict]:
        """Get all messages for a session, returned as role/content dicts for Redis hydration."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [{"role": m.role, "content": m.content} for m in rows]

    async def create_message(
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
        vector_ids: list[str] | None = None,
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
            vector_ids=vector_ids,
        )
        self.session.add(msg)
        # Touch session updated_at so sidebar ordering reflects activity
        stmt = update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now())
        await self.session.execute(stmt)
        await self.session.commit()
        await self.session.refresh(msg)
        return self._message_to_dict(msg)

    async def save_user_message(self, session_id: str, content: str) -> None:
        """Save a user message and touch the session."""
        self.session.add(ChatMessage(session_id=session_id, role="user", content=content))
        stmt = update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now())
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_feedback(self, message_id: str, feedback: int) -> dict | None:
        """Update feedback for a message. Returns the updated message dict."""
        msg = await self.session.get(ChatMessage, message_id)
        if msg is None:
            return None
        msg.feedback = feedback
        await self.session.commit()
        await self.session.refresh(msg)
        return self._message_to_dict(msg)

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
            "feedback": m.feedback,
            "vector_ids": m.vector_ids or [],
            "created_at": m.created_at.isoformat(),
        }

    async def get_feedback_signals(self, session_id: str, limit: int = 10) -> tuple[list[str], list[str]]:
        """Get positive and negative vector IDs from recent feedback in this session."""
        stmt = (
            select(ChatMessage.feedback, ChatMessage.vector_ids)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.feedback != 0)
            .where(ChatMessage.vector_ids.isnot(None))
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        positive = []
        negative = []
        for feedback, vids in rows:
            if vids:
                if feedback > 0:
                    positive.extend(vids)
                else:
                    negative.extend(vids)
        return list(set(positive)), list(set(negative))

    async def delete_sessions_older_than(self, cutoff: datetime) -> int:
        """Bulk-delete old chat sessions. CASCADE deletes messages. Returns count."""
        stmt = delete(ChatSession).where(ChatSession.created_at < cutoff)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
