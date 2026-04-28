"""User memory service — ChatGPT-like persistent memory.

Stores per-user facts, preferences, corrections, and instructions
learned from conversations. Injected into system prompt for personalized responses.

Memory types:
  - preference: User preferences (e.g., "likes detailed answers")
  - correction: User corrections (e.g., "don't use bullet points")
  - instruction: Explicit instructions (e.g., "always cite sources")
  - fact: Facts about user (e.g., "works in marketing")
"""

from __future__ import annotations

import json
import logging
import re

import redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.memory import UserMemory

logger = logging.getLogger(__name__)

# Redis cache TTL for user memories (5 minutes)
_MEMORY_CACHE_TTL = 300


class UserMemoryService:
    """Manages persistent user memories with Redis caching."""

    def __init__(self) -> None:
        self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def _cache_key(self, user_id: str) -> str:
        return f"user_memories:{user_id}"

    def get_active_memories(self, user_id: str) -> list[dict[str, str]]:
        """Get active memories for a user (Redis cache → PostgreSQL fallback)."""
        # Try Redis cache first
        cache_key = self._cache_key(user_id)
        try:
            cached = self._redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            logger.warning("Redis cache miss for user memories: %s", user_id)

        # Fallback to PostgreSQL
        with SessionLocal() as session:
            rows = (
                session.query(UserMemory)
                .filter(UserMemory.user_id == user_id, UserMemory.is_active.is_(True))
                .order_by(UserMemory.created_at.desc())
                .limit(50)
                .all()
            )
            memories = [{"type": row.memory_type, "content": row.content} for row in rows]

        # Cache in Redis
        try:
            self._redis.setex(cache_key, _MEMORY_CACHE_TTL, json.dumps(memories, ensure_ascii=False))
        except Exception as e:
            logger.debug("Failed to cache user memories: %s", e)

        return memories

    def format_memories_for_prompt(self, user_id: str) -> str:
        """Format user memories for injection into system prompt."""
        memories = self.get_active_memories(user_id)
        if not memories:
            return ""

        lines = []
        for m in memories:
            prefix = {
                "preference": "Sở thích",
                "correction": "Sửa đổi",
                "instruction": "Chỉ dẫn",
                "fact": "Thông tin",
            }.get(m["type"], "Ghi nhớ")
            lines.append(f"- [{prefix}] {m['content']}")

        return "THÔNG TIN ĐÃ GHI NHỚ VỀ NGƯỜI DÙNG:\n" + "\n".join(lines)

    def add_memory(self, user_id: str, memory_type: str, content: str) -> None:
        """Store a new memory for the user."""
        with SessionLocal() as session:
            session.add(
                UserMemory(
                    user_id=user_id,
                    memory_type=memory_type,
                    content=content,
                )
            )
            session.commit()

        # Invalidate cache
        self._invalidate_cache(user_id)
        logger.info("Added %s memory for user %s: %s", memory_type, user_id[:8], content[:80])

    def _invalidate_cache(self, user_id: str) -> None:
        try:
            self._redis.delete(self._cache_key(user_id))
        except Exception as e:
            logger.debug("Failed to invalidate memory cache: %s", e)

    def should_extract_memory(self, user_message: str) -> bool:
        """Quick heuristic to detect if user message contains feedback worth remembering."""
        if not user_message:
            return False

        # Explicit memory triggers
        explicit_patterns = [
            r"nhớ(?: là| rằng| cho tôi)?",
            r"hãy nhớ",
            r"remember",
            r"ghi nhớ",
            r"lưu ý",
        ]
        # Correction/feedback triggers
        correction_patterns = [
            r"sai(?: rồi| mất)?",
            r"không(?: phải)? (?:vậy|thế|đúng)",
            r"đừng",
            r"không muốn",
            r"tôi (?:thích|muốn|cần|yêu cầu)",
            r"ý tôi là",
            r"tôi nói (?:là|rằng)",
            r"bạn (?:nên|phải|hãy)",
            r"sửa lại",
            r"cải thiện",
            r"tốt hơn",
        ]

        msg_lower = user_message.lower()
        for pattern in explicit_patterns + correction_patterns:
            if re.search(pattern, msg_lower):
                return True

        return False

    async def extract_memories_from_turn(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Extract memorable facts from a conversation turn using Gemini.

        Called asynchronously after the chat response is complete.
        """
        if not self.should_extract_memory(user_message):
            return

        try:
            from app.adapters.ai import build_ai_provider

            provider = build_ai_provider()
            extraction_prompt = (
                "Phân tích tin nhắn người dùng sau và trích xuất các thông tin đáng nhớ. "
                "Chỉ trích xuất nếu người dùng đưa ra sở thích, sửa đổi, chỉ dẫn, hoặc thông tin cá nhân.\n\n"
                f"Tin nhắn người dùng: {user_message}\n\n"
                "Trả về JSON array (hoặc mảng rỗng [] nếu không có gì đáng nhớ):\n"
                '[{"type": "preference|correction|instruction|fact", "content": "..."}]\n\n'
                "QUAN TRỌNG: Chỉ trả về JSON, không thêm gì khác."
            )

            result = await provider.chat(
                [{"role": "user", "content": extraction_prompt}],
                context=[],
                citations=[],
            )
            text = result.get("answer", "")
            if not text:
                return

            # Parse JSON from response
            json_start = text.find("[")
            json_end = text.rfind("]") + 1
            if json_start < 0 or json_end <= json_start:
                return

            memories = json.loads(text[json_start:json_end])
            for m in memories:
                if isinstance(m, dict) and m.get("content") and m.get("type"):
                    content = str(m["content"]).strip()
                    memory_type = str(m["type"]).strip()
                    if content and memory_type in ("preference", "correction", "instruction", "fact"):
                        self.add_memory(user_id, memory_type, content)

        except Exception as e:
            logger.warning("Memory extraction failed: %s", e, exc_info=True)
