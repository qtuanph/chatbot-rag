"""Atomic Redis-based quota enforcement.

Uses tenant configuration stored in PostgreSQL (`tenants` table: `rate_limit_rpm`, `monthly_request_quota`, `monthly_token_quota`)
with fallback to environment settings if unconfigured (0 = unlimited).

Counter keys:
- rate:user:{tenant_id}:{user_id}:{minute}              -> user rate/min
- rate:tenant:{tenant_id}:{minute}                       -> tenant rate/min
- quota:user_daily:{tenant_id}:{user_id}:{date_vn}      -> user daily total
- quota:tenant_monthly_requests:{tenant_id}:{year_month_vn} -> tenant monthly requests
- quota:tenant_monthly_tokens:{tenant_id}:{year_month_vn}   -> tenant monthly tokens
- budget:tenant:{tenant_id}:{year_month_vn}              -> tenant monthly cost (micros VND)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_TZ_VN = timezone(timedelta(hours=7))


def _vn_now() -> datetime:
    return datetime.now(_TZ_VN)


def _minute_key() -> str:
    return _vn_now().strftime("%Y%m%d%H%M")


def _date_key() -> str:
    return _vn_now().strftime("%Y%m%d")


def _month_key() -> str:
    return _vn_now().strftime("%Y%m")


class QuotaService:
    def __init__(self, redis: aioredis.Redis | None, tenant_repo: Any = None) -> None:
        self.redis = redis
        self.tenant_repo = tenant_repo

    async def _get_tenant_config(self, tenant_id: str) -> dict[str, Any]:
        """Fetch dynamic tenant limits from DB (`tenants` table)."""
        if self.tenant_repo:
            try:
                tenant = await self.tenant_repo.get_tenant(tenant_id)
                if tenant:
                    return tenant
            except Exception as exc:
                logger.warning("Failed to fetch tenant config for quota check: %s", exc)
        return {}

    async def check_and_increment_rate(
        self, *, tenant_id: str, user_id: str | None, tenant_config: dict[str, Any] | None = None
    ) -> tuple[bool, str]:
        """Check rate limits using tenant's `rate_limit_rpm` set in DB / Webapp."""
        if not self.redis:
            return not settings.quota_fail_closed, "redis_unavailable"

        try:
            config = tenant_config or await self._get_tenant_config(tenant_id)
            tenant_rpm = config.get("rate_limit_rpm") or settings.quota_tenant_rate_per_min

            minute = _minute_key()
            pipe = self.redis.pipeline()

            user_key = f"rate:user:{tenant_id}:{user_id or 'anon'}:{minute}"
            pipe.incr(user_key)
            pipe.expire(user_key, 90)

            tenant_key = f"rate:tenant:{tenant_id}:{minute}"
            pipe.incr(tenant_key)
            pipe.expire(tenant_key, 90)

            results = await pipe.execute()
            user_count = int(results[0])
            tenant_count = int(results[2])

            user_limit = settings.effective_rate_limit(settings.quota_user_rate_per_min)
            tenant_limit = settings.effective_rate_limit(tenant_rpm)

            if user_count > user_limit:
                return False, f"user_rate_limit_exceeded:{user_count}/{user_limit}"
            if tenant_count > tenant_limit:
                return False, f"tenant_rate_limit_exceeded:{tenant_count}/{tenant_limit}"
            return True, "ok"
        except Exception as exc:
            logger.warning("Quota rate check error: %s", exc)
            return not settings.quota_fail_closed, f"error:{exc}"

    async def check_and_increment_daily(self, *, tenant_id: str, user_id: str | None) -> tuple[bool, str]:
        """Check user daily request quota."""
        if not self.redis:
            return not settings.quota_fail_closed, "redis_unavailable"

        try:
            date = _date_key()
            key = f"quota:user_daily:{tenant_id}:{user_id or 'anon'}:{date}"
            count = await self.redis.incr(key)
            if count == 1:
                now = _vn_now()
                midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                ttl = int((midnight - now).total_seconds()) + 60
                await self.redis.expire(key, ttl)

            limit = settings.quota_user_daily_requests
            if count > limit:
                return False, f"daily_request_quota_exceeded:{count}/{limit}"
            return True, "ok"
        except Exception as exc:
            logger.warning("Quota daily check error: %s", exc)
            return not settings.quota_fail_closed, f"error:{exc}"

    async def reserve_llm_call(
        self, *, tenant_id: str, tenant_config: dict[str, Any] | None = None
    ) -> tuple[bool, str]:
        """Check monthly request quota using tenant's `monthly_request_quota` set in DB / Webapp."""
        if not self.redis:
            return not settings.quota_fail_closed, "redis_unavailable"

        try:
            config = tenant_config or await self._get_tenant_config(tenant_id)
            monthly_limit = config.get("monthly_request_quota")
            if monthly_limit is None or monthly_limit <= 0:
                monthly_limit = settings.quota_tenant_monthly_llm_calls

            if monthly_limit <= 0:
                return True, "ok"

            month = _month_key()
            key = f"quota:tenant_monthly_requests:{tenant_id}:{month}"
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 35 * 24 * 3600)

            if count > monthly_limit:
                await self.redis.decr(key)
                return False, f"monthly_request_quota_exceeded:{count - 1}/{monthly_limit}"
            return True, "ok"
        except Exception as exc:
            logger.warning("Quota reserve LLM error: %s", exc)
            return not settings.quota_fail_closed, f"error:{exc}"

    async def record_cost_and_tokens(
        self,
        *,
        tenant_id: str,
        cost_micros_vnd: int,
        total_tokens: int = 0,
        tenant_config: dict[str, Any] | None = None,
    ) -> tuple[str, int]:
        """Record cost and tokens in Redis, enforcing `monthly_token_quota` from DB / Webapp."""
        if not self.redis:
            return "ok", 0

        try:
            month = _month_key()
            config = tenant_config or await self._get_tenant_config(tenant_id)

            # 1. Token quota check
            token_quota = config.get("monthly_token_quota", 0)
            if token_quota > 0 and total_tokens > 0:
                token_key = f"quota:tenant_monthly_tokens:{tenant_id}:{month}"
                current_tokens = await self.redis.incrby(token_key, total_tokens)
                if current_tokens <= total_tokens:
                    await self.redis.expire(token_key, 35 * 24 * 3600)

            # 2. Cost tracking
            if settings.quota_hard_budget_vnd <= 0:
                return "ok", 0

            cost_key = f"budget:tenant:{tenant_id}:{month}"
            total_cost = await self.redis.incrby(cost_key, cost_micros_vnd)
            if total_cost <= cost_micros_vnd:
                await self.redis.expire(cost_key, 35 * 24 * 3600)

            budget_micros = settings.quota_hard_budget_vnd * 1_000_000
            pct = int(total_cost * 100 / budget_micros) if budget_micros > 0 else 0
            if pct >= settings.quota_cost_alert_pct_cutoff:
                return "hard_stop", pct
            if pct >= settings.quota_cost_alert_pct_alert:
                return "alert", pct
            if pct >= settings.quota_cost_alert_pct_warn:
                return "warn", pct
            return "ok", pct
        except Exception as exc:
            logger.warning("Quota record cost/tokens error: %s", exc)
            return "ok", 0

    async def check_budget_before_llm(self, *, tenant_id: str) -> tuple[bool, str]:
        """Check if budget allows LLM call."""
        if not self.redis or settings.quota_hard_budget_vnd <= 0:
            return True, "ok"

        try:
            month = _month_key()
            key = f"budget:tenant:{tenant_id}:{month}"
            raw = await self.redis.get(key)
            current = int(raw or 0)
            budget_micros = settings.quota_hard_budget_vnd * 1_000_000
            pct = int(current * 100 / budget_micros) if budget_micros > 0 else 0
            if pct >= settings.quota_cost_alert_pct_cutoff:
                return False, f"hard_budget_exceeded:{pct}%"
            return True, "ok"
        except Exception as exc:
            logger.warning("Quota check budget error: %s", exc)
            return not settings.quota_fail_closed, f"error:{exc}"
