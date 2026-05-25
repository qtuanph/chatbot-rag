import sqlite3
from typing import Any

from app.modules.settings.database import get_db


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
        return [dict(r) for r in rows]

    def get_provider(self, provider_id: int) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM ai_providers WHERE id = ?", (provider_id,)).fetchone()
        return dict(row) if row else None

    def create_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        cur = self.db.execute(
            """INSERT INTO ai_providers
               (service_type, provider_name, display_name, url, model, api_key, is_active, is_builtin, priority)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)""",
            (
                data["service_type"],
                data["provider_name"],
                data["display_name"],
                data.get("url", ""),
                data.get("model", ""),
                data.get("api_key", ""),
                data.get("priority", 0),
            ),
        )
        self.db.commit()
        return self.get_provider(cur.lastrowid)

    def update_provider(self, provider_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        fields = []
        values = []
        for key in ("display_name", "url", "model", "api_key", "priority", "is_active"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
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
        return dict(row) if row else None

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
        keys = self.db.execute(
            "SELECT id, key_value, failure_count FROM api_keys WHERE provider_id = ? AND is_active = 1 ORDER BY last_used_at ASC NULLS FIRST",
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
