from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_vietnam_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(VIETNAM_TZ)


def to_vietnam_iso(value: datetime | None) -> str | None:
    localized = to_vietnam_datetime(value)
    return localized.isoformat() if localized else None
