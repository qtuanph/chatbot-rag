from dataclasses import dataclass


@dataclass(frozen=True)
class TenantApiContext:
    tenant_id: str
    api_key_id: str
    request_id: str = ""
