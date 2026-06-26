from __future__ import annotations

from app.core import http_errors
from app.modules.auth.context import AuthContext


def resolve_strict_tenant_scope(auth: AuthContext, requested_tenant_id: str | None = None) -> str | None:
    """
    Resolve the effective tenant_id for strict API endpoints (e.g. lists, creation).
    Raises HTTP 403 Forbidden if a user attempts to access a tenant they do not belong to.
    """
    effective_tenant_id = requested_tenant_id
    if auth.role != "platform_admin":
        if not auth.tenant_id:
            raise http_errors.forbidden("Tenant context is required")
        if requested_tenant_id and requested_tenant_id != auth.tenant_id:
            raise http_errors.forbidden("You can only access resources in your own tenant")
        effective_tenant_id = auth.tenant_id
    return effective_tenant_id


def resolve_loose_tenant_scope(auth: AuthContext) -> str | None:
    """
    Resolve the tenant scope for retrieving specific records (e.g. GET by ID).
    Platform admins return None (meaning no tenant filter is applied).
    Regular users return their own tenant_id to scope the DB query.
    """
    return None if auth.role == "platform_admin" else auth.tenant_id
