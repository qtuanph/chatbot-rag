"""Admin-only conversation repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import desc, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationMessage


def _safe_uuid(val: Any) -> uuid.UUID | None:
    if isinstance(val, uuid.UUID):
        return val
    if isinstance(val, str) and val:
        try:
            return uuid.UUID(val)
        except (ValueError, AttributeError):
            return None
    return None


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_conversation(self, *, tenant_id: str, conversation_id: str, retention_days: int = 90) -> str:
        """Get or create conversation; returns PK UUID str."""
        parsed_tenant = _safe_uuid(tenant_id)
        if not parsed_tenant:
            return ""
        expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)
        stmt = (
            pg_insert(Conversation)
            .values(
                tenant_id=parsed_tenant,
                conversation_id=conversation_id,
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                constraint="uq_conv_tenant_convid",
                set_={"last_message_at": func.now(), "expires_at": expires_at},
            )
            .returning(Conversation.id)
        )
        result = await self.session.execute(stmt)
        return str(result.scalar_one())


    async def add_message(
        self,
        *,
        conversation_pk: str,
        tenant_id: str,
        role: str,
        content: str,
        **kwargs,
    ) -> str:
        """Insert a message row; returns PK UUID str."""
        parsed_pk = _safe_uuid(conversation_pk)
        parsed_tenant = _safe_uuid(tenant_id)
        if not parsed_pk or not parsed_tenant:
            return ""
        msg = ConversationMessage(
            conversation_pk=parsed_pk,
            tenant_id=parsed_tenant,
            role=role,
            content=content,
            **{k: v for k, v in kwargs.items() if hasattr(ConversationMessage, k)},
        )
        self.session.add(msg)
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == parsed_pk)
            .values(message_count=Conversation.message_count + 1, last_message_at=func.now())
        )

        await self.session.flush()
        return str(msg.id)

    async def list_conversations(
        self, *, tenant_id: str | None = None, offset: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        """List recorded conversations for Admin Audit."""
        stmt = select(Conversation)
        count_stmt = select(func.count(Conversation.id))
        if tenant_id:
            tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
            stmt = stmt.where(Conversation.tenant_id == tid)
            count_stmt = count_stmt.where(Conversation.tenant_id == tid)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(desc(Conversation.last_message_at)).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()

        items = []
        for c in rows:
            items.append(
                {
                    "id": str(c.id),
                    "tenant_id": str(c.tenant_id),
                    "conversation_id": c.conversation_id,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
                    "message_count": c.message_count,
                }
            )
        return items, total

    async def get_messages(self, conversation_id: str, *, tenant_id: str | None = None) -> list[dict]:
        """Get all messages for a specific conversation_id for Admin Audit."""
        stmt = select(ConversationMessage).join(Conversation, Conversation.id == ConversationMessage.conversation_pk)
        stmt = stmt.where(Conversation.conversation_id == conversation_id)
        if tenant_id:
            tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
            stmt = stmt.where(ConversationMessage.tenant_id == tid)

        stmt = stmt.order_by(ConversationMessage.created_at.asc())
        rows = (await self.session.execute(stmt)).scalars().all()

        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "model_name": m.model_name,
                "prompt_tokens": m.prompt_tokens,
                "completion_tokens": m.completion_tokens,
                "latency_ms": m.latency_ms,
                "cost_micros_vnd": m.cost_micros_vnd,
                "is_cache_hit": m.is_cache_hit,
                "cached_type": m.cached_type,
                "citations": m.citations,
                "no_answer": m.no_answer,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ]
