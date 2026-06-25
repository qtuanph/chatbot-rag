import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.modules.settings.database import get_db


def _row_to_provider(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if isinstance(d.get("config"), str):
        d["config"] = json.loads(d["config"]) if d["config"] else {}
    return d


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SettingsRepository:
    def __init__(self) -> None:
        self._db: sqlite3.Connection | None = None

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = get_db()
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    # ── Providers ─────────────────────────────────────────────────────

    def list_providers(self, service_type: str | None = None) -> list[dict[str, Any]]:
        if service_type:
            rows = self.db.execute(
                "SELECT * FROM ai_providers WHERE service_type = ? ORDER BY priority",
                (service_type,),
            ).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM ai_providers ORDER BY service_type, priority").fetchall()
        return [_row_to_provider(r) for r in rows]

    def get_provider(self, provider_id: int) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM ai_providers WHERE id = ?", (provider_id,)).fetchone()
        return _row_to_provider(row) if row else None

    def create_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        config_json = json.dumps(data.get("config", {}))
        cur = self.db.execute(
            """INSERT INTO ai_providers
               (service_type, provider_name, display_name, url, model, api_key, is_active, is_builtin, priority, config)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
            (
                data["service_type"],
                data["provider_name"],
                data["display_name"],
                data.get("url", ""),
                data.get("model", ""),
                data.get("api_key", ""),
                data.get("priority", 0),
                config_json,
            ),
        )
        self.db.commit()
        return self.get_provider(cur.lastrowid)

    def update_provider(self, provider_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        fields = []
        values = []
        for key in (
            "display_name",
            "url",
            "model",
            "api_key",
            "priority",
            "is_active",
            "last_test_status",
            "last_test_at",
            "last_error",
            "last_error_at",
        ):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if "config" in data:
            fields.append("config = ?")
            values.append(json.dumps(data["config"]))
        if not fields:
            return self.get_provider(provider_id)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(provider_id)
        self.db.execute(f"UPDATE ai_providers SET {', '.join(fields)} WHERE id = ?", values)
        self.db.commit()
        return self.get_provider(provider_id)

    def delete_provider(self, provider_id: int) -> bool:
        cur = self.db.execute("DELETE FROM ai_providers WHERE id = ? AND is_builtin = 0", (provider_id,))
        self.db.commit()
        return cur.rowcount > 0

    def activate_provider(self, provider_id: int) -> dict[str, Any] | None:
        provider = self.get_provider(provider_id)
        if not provider:
            return None
        self.db.execute(
            "UPDATE ai_providers SET is_active = 0 WHERE service_type = ?",
            (provider["service_type"],),
        )
        self.db.execute(
            "UPDATE ai_providers SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (provider_id,),
        )
        self.db.commit()
        return self.get_provider(provider_id)

    def get_active_provider(self, service_type: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM ai_providers WHERE service_type = ? AND is_active = 1 LIMIT 1",
            (service_type,),
        ).fetchone()
        return _row_to_provider(row) if row else None

    def get_builtin_provider(self, service_type: str, provider_name: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM ai_providers WHERE service_type = ? AND provider_name = ? AND is_builtin = 1 LIMIT 1",
            (service_type, provider_name),
        ).fetchone()
        return _row_to_provider(row) if row else None

    def update_provider_test_status(self, provider_id: int, success: bool, error_message: str = "") -> None:
        now = _now_iso()
        self.db.execute(
            """UPDATE ai_providers
               SET last_test_status = ?, last_test_at = ?, last_error = ?, last_error_at = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            ("success" if success else "failed", now, error_message, now if error_message else None, provider_id),
        )
        self.db.commit()

    # ── API Keys ──────────────────────────────────────────────────────

    def list_keys(self, provider_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM api_keys WHERE provider_id = ? ORDER BY created_at", (provider_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def create_key(self, provider_id: int, key_value: str) -> dict[str, Any]:
        cur = self.db.execute(
            "INSERT INTO api_keys (provider_id, key_value) VALUES (?, ?)",
            (provider_id, key_value),
        )
        self.db.commit()
        return dict(self.db.execute("SELECT * FROM api_keys WHERE id = ?", (cur.lastrowid,)).fetchone())

    def delete_key(self, provider_id: int, key_id: int) -> bool:
        cur = self.db.execute("DELETE FROM api_keys WHERE id = ? AND provider_id = ?", (key_id, provider_id))
        self.db.commit()
        return cur.rowcount > 0

    def get_next_key(self, provider_id: int) -> str | None:
        """Round-robin key selection that skips rate-limited keys."""
        now = _now_iso()
        # Reset expired rate limits first
        self.db.execute(
            """UPDATE api_keys
               SET rate_limited_until = NULL, backoff_level = 0
               WHERE provider_id = ? AND rate_limited_until IS NOT NULL AND rate_limited_until <= ?""",
            (provider_id, now),
        )
        self.db.commit()
        # Pick least-recently-used key that isn't rate-limited
        keys = self.db.execute(
            """SELECT id, key_value, failure_count, rate_limited_until
               FROM api_keys
               WHERE provider_id = ? AND is_active = 1
                 AND (rate_limited_until IS NULL OR rate_limited_until <= ?)
               ORDER BY last_used_at ASC NULLS FIRST""",
            (provider_id, now),
        ).fetchall()
        if not keys:
            # All keys rate-limited — use the one expiring soonest
            keys = self.db.execute(
                """SELECT id, key_value, failure_count, rate_limited_until
                   FROM api_keys
                   WHERE provider_id = ? AND is_active = 1
                   ORDER BY rate_limited_until ASC NULLS LAST
                   LIMIT 1""",
                (provider_id,),
            ).fetchall()
        if not keys:
            return None
        key = keys[0]
        self.db.execute(
            "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
            (key["id"],),
        )
        self.db.commit()
        return key["key_value"]

    def mark_key_failure(self, key_id: int) -> None:
        self.db.execute("UPDATE api_keys SET failure_count = failure_count + 1 WHERE id = ?", (key_id,))
        self.db.commit()

    def mark_key_rate_limited(
        self, key_id: int, backoff_base_ms: int = 2000, max_backoff_ms: int = 300000, max_level: int = 15
    ) -> None:
        """Apply exponential backoff to a key and set rate_limited_until."""
        row = self.db.execute("SELECT backoff_level FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        if not row:
            return
        level = min(row["backoff_level"] + 1, max_level)
        delay_ms = min(backoff_base_ms * (2 ** (level - 1)), max_backoff_ms)
        # Add delay as ISO duration — we store absolute timestamp
        from datetime import timedelta

        until_dt = datetime.now(timezone.utc) + timedelta(milliseconds=delay_ms)
        self.db.execute(
            """UPDATE api_keys SET
               backoff_level = ?, rate_limited_until = ?, failure_count = failure_count + 1
               WHERE id = ?""",
            (level, until_dt.isoformat(), key_id),
        )
        self.db.commit()

    def mark_key_success(self, key_id: int) -> None:
        """Reset rate limit state on successful call."""
        self.db.execute(
            """UPDATE api_keys SET
               backoff_level = 0, rate_limited_until = NULL, last_error = '', last_error_at = NULL
               WHERE id = ?""",
            (key_id,),
        )
        self.db.commit()
