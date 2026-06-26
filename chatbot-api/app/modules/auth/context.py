from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    role: str
    token_id: str
    tenant_id: str | None = None
    actor_type: str = "platform_user"
    api_key_id: str | None = None
    request_id: str = ""
