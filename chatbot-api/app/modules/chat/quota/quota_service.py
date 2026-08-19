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


def _get_rtm_billing(key: str, default: str) -> int:
    try:
        from app.modules.settings.runtime_manager import RuntimeProviderManager

        val = RuntimeProviderManager.get_instance().get_billing(key, default)
        return int(val) if val else int(default)
    except Exception:
        return int(default)


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
        """Check rate limits.

        - If user_id is provided (internal/JWT auth): enforce both per-user limit AND tenant limit.
        - If user_id is None (public API key auth): enforce ONLY tenant limit (rate_limit_rpm from DB).
          Tenant admin sets the single limit for the whole tenant in /admin/tenants.
        """
        if not self.redis:
            return not settings.quota_fail_closed, "redis_unavailable"

        try:
            config = tenant_config or await self._get_tenant_config(tenant_id)
            tenant_rpm = config.get("rate_limit_rpm") or settings.quota_tenant_rate_per_min

            minute = _minute_key()
            pipe = self.redis.pipeline()

            # Only track per-user counter when we have an actual user identity
            if user_id is not None:
                user_key = f"rate:user:{tenant_id}:{user_id}:{minute}"
                pipe.incr(user_key)
                pipe.expire(user_key, 90)

            tenant_key = f"rate:tenant:{tenant_id}:{minute}"
            pipe.incr(tenant_key)
            pipe.expire(tenant_key, 90)

            results = await pipe.execute()

            if user_id is not None:
                user_count = int(results[0])
                tenant_count = int(results[2])
                quota_user_rate = _get_rtm_billing("quota_user_rate_per_min", str(settings.quota_user_rate_per_min))
                user_limit = settings.effective_rate_limit(quota_user_rate)
                if user_count > user_limit:
                    return False, f"user_rate_limit_exceeded:{user_count}/{user_limit}"
            else:
                # Public API: only tenant limit matters
                tenant_count = int(results[0])

            tenant_limit = settings.effective_rate_limit(tenant_rpm)
            if tenant_count > tenant_limit:
                return False, f"tenant_rate_limit_exceeded:{tenant_count}/{tenant_limit}"
            return True, "ok"
        except Exception as exc:
            logger.warning("Quota rate check error: %s", exc)
            return not settings.quota_fail_closed, f"error:{exc}"

    async def check_and_increment_daily(self, *, tenant_id: str, user_id: str | None) -> tuple[bool, str]:
        """Check user daily request quota or tenant daily request quota."""
        if not self.redis:
            return not settings.quota_fail_closed, "redis_unavailable"

        try:
            date = _date_key()
            now = _vn_now()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            ttl = int((midnight - now).total_seconds()) + 60

            if user_id is None:
                # M-13: check tenant-level daily limit
                key = f"quota:tenant_daily:{tenant_id}:{date}"
                pipe = self.redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, ttl)
                results = await pipe.execute()
                count = int(results[0])
                limit = _get_rtm_billing("quota_tenant_daily_requests", "0")
                if limit > 0 and count > limit:
                    return False, f"tenant_daily_request_quota_exceeded:{count}/{limit}"
                return True, "ok"
            else:
                key = f"quota:user_daily:{tenant_id}:{user_id}:{date}"
                pipe = self.redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, ttl)
                results = await pipe.execute()
                count = int(results[0])

                limit = _get_rtm_billing("quota_user_daily_requests", str(settings.quota_user_daily_requests))
                if limit > 0 and count > limit:
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

            # M-12: Use Lua script for atomic check-and-increment
            script = """
            local current = redis.call('GET', KEYS[1])
            if current == false then current = 0 else current = tonumber(current) end
            if current >= tonumber(ARGV[1]) then return -1 end
            redis.call('INCRBY', KEYS[1], 1)
            redis.call('EXPIRE', KEYS[1], ARGV[2])
            return current + 1
            """
            result = await self.redis.eval(script, 1, key, monthly_limit, 35 * 24 * 3600)

            if result == -1:
                return False, f"monthly_request_quota_exceeded:limit_reached/{monthly_limit}"

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
            pipe = self.redis.pipeline()

            # 1. Token quota check
            token_quota = config.get("monthly_token_quota", 0)
            token_index: int | None = None
            if token_quota > 0 and total_tokens > 0:
                token_key = f"quota:tenant_monthly_tokens:{tenant_id}:{month}"
                token_index = len(pipe)
                pipe.incrby(token_key, total_tokens)
                pipe.expire(token_key, 35 * 24 * 3600)

            # 2. Cost tracking — track cost_index BEFORE appending to pipeline (L-04 fix).
            hard_budget_vnd = _get_rtm_billing("quota_hard_budget_vnd", str(settings.quota_hard_budget_vnd))
            cost_key = f"budget:tenant:{tenant_id}:{month}"
            cost_index: int | None = None
            if hard_budget_vnd > 0 and cost_micros_vnd > 0:
                cost_index = len(pipe)  # explicit index of the INCRBY result
                pipe.incrby(cost_key, cost_micros_vnd)
                pipe.expire(cost_key, 35 * 24 * 3600)

            if len(pipe) > 0:
                results = await pipe.execute()
                total_cost = int(results[cost_index]) if cost_index is not None else 0
                if token_index is not None:
                    current_tokens = int(results[token_index])
                    # C-4: check if tokens exceeded limit and log warning
                    if current_tokens > token_quota:
                        logger.warning(
                            "Tenant %s exceeded monthly_token_quota: %d > %d", tenant_id, current_tokens, token_quota
                        )
            else:
                total_cost = 0

            budget_micros = hard_budget_vnd * 1_000_000
            pct = int(total_cost * 100 / budget_micros) if budget_micros > 0 else 0

            cutoff_pct = _get_rtm_billing("quota_cost_alert_pct_cutoff", str(settings.quota_cost_alert_pct_cutoff))
            alert_pct = _get_rtm_billing("quota_cost_alert_pct_alert", str(settings.quota_cost_alert_pct_alert))
            warn_pct = _get_rtm_billing("quota_cost_alert_pct_warn", str(settings.quota_cost_alert_pct_warn))

            if pct >= cutoff_pct:
                return "hard_stop", pct
            if pct >= alert_pct:
                return "alert", pct
            if pct >= warn_pct:
                return "warn", pct
            return "ok", pct
        except Exception as exc:
            logger.warning("Quota record cost/tokens error: %s", exc)
            return "ok", 0

    async def check_budget_before_llm(self, *, tenant_id: str) -> tuple[bool, str]:
        """Check if budget allows LLM call."""
        hard_budget_vnd = _get_rtm_billing("quota_hard_budget_vnd", str(settings.quota_hard_budget_vnd))
        if not self.redis or hard_budget_vnd <= 0:
            return True, "ok"

        try:
            month = _month_key()
            key = f"budget:tenant:{tenant_id}:{month}"
            raw = await self.redis.get(key)
            current = int(raw or 0)
            budget_micros = hard_budget_vnd * 1_000_000
            pct = int(current * 100 / budget_micros) if budget_micros > 0 else 0

            cutoff_pct = _get_rtm_billing("quota_cost_alert_pct_cutoff", str(settings.quota_cost_alert_pct_cutoff))
            if pct >= cutoff_pct:
                return False, f"hard_budget_exceeded:{pct}%"
            return True, "ok"
        except Exception as exc:
            logger.warning("Quota check budget error: %s", exc)
            return not settings.quota_fail_closed, f"error:{exc}"

    async def refund_llm_call(self, *, tenant_id: str) -> None:
        """H-11: Decrement monthly request counter when LLM fails without producing output.

        Called when reserve_llm_call() was already invoked but the actual LLM call failed
        (timeout, connection error, etc.) so no tokens were consumed.
        """
        if not self.redis:
            return
        try:
            month = _month_key()
            key = f"quota:tenant_monthly_requests:{tenant_id}:{month}"
            new_val = await self.redis.decr(key)
            # Ensure counter never goes below 0 due to race conditions.
            if int(new_val or 0) < 0:
                await self.redis.set(key, 0, keepttl=True)
            logger.debug("Refunded LLM call quota for tenant %s (counter=%s)", tenant_id, new_val)
        except Exception as exc:
            logger.warning("quota.refund_llm_call error: %s", exc)
