"""Auth service — authentication and user management business logic."""

from __future__ import annotations

import logging

from app.modules.auth.repository import AuthRepository
from app.modules.auth.utils.auth import create_access_token, hash_password, verify_password
from app.modules.auth.utils.token_blacklist import TokenBlacklist
from app.utils.audit import safe_record_audit

logger = logging.getLogger(__name__)


class AuthService:
    """Business logic for authentication and user management."""

    def __init__(self, repo: AuthRepository, blacklist: TokenBlacklist) -> None:
        self.repo = repo
        self.blacklist = blacklist

    async def login(
        self, *, username: str, password: str, ip_address: str | None = None, user_agent: str | None = None
    ) -> dict:
        """Authenticate user and return token + role. Raises ValueError on failure."""
        normalized = username.strip()
        user = await self.repo.get_user_by_username(normalized, include_hash=True)
        if user is None or not verify_password(password, user["password_hash"]):
            raise ValueError("Invalid username or password")

        role = await self.repo.get_role_by_id(user["role_id"])
        if role is None:
            raise ValueError("User has no assigned role")

        token = create_access_token(subject=user["id"], role=role["name"], tenant_id=user.get("tenant_id"))

        safe_record_audit(
            action="auth.login",
            actor_user_id=user["id"],
            subject_type="user",
            subject_id=user["id"],
            ip_address=ip_address,
            user_agent=user_agent,
            details={"role": role["name"]},
            redis_client_override=self.blacklist.client,
        )

        return {
            "access_token": token,
            "role": role["name"],
            "user_id": user["id"],
            "tenant_id": user.get("tenant_id"),
        }

    async def logout(
        self, *, jti: str, expires_at: int, user_id: str, ip_address: str | None = None, user_agent: str | None = None
    ) -> None:
        """Revoke a JWT token."""
        await self.blacklist.revoke(jti, expires_at)
        safe_record_audit(
            action="auth.logout",
            actor_user_id=user_id,
            subject_type="token",
            subject_id=jti,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"expires_at": expires_at},
            redis_client_override=self.blacklist.client,
        )

    async def create_user(
        self,
        *,
        username: str,
        password: str,
        role_name: str,
        admin_user_id: str,
        tenant_id: str | None = None,
    ) -> dict:
        """Create a new user. Returns user dict. Raises on conflict/invalid role."""
        from sqlalchemy.exc import IntegrityError

        normalized = username.strip()

        # Check duplicate
        existing = await self.repo.get_user_by_username(normalized)
        if existing is not None:
            raise ValueError("Username already exists")

        # Validate role
        role = await self.repo.get_role_by_name(role_name)
        if role is None:
            raise ValueError("Invalid role")
        if role["name"] == "tenant_admin" and not tenant_id:
            raise ValueError("tenant_id is required for tenant_admin users")
        if role["name"] == "platform_admin":
            tenant_id = None

        # Validate password strength
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")

        try:
            user = await self.repo.create_user_with_tenant(
                username=normalized,
                password_hash=hash_password(password),
                role_id=role["id"],
                tenant_id=tenant_id,
            )
        except IntegrityError:
            raise ValueError("Username already exists") from None

        safe_record_audit(
            action="auth.user.create",
            actor_user_id=admin_user_id,
            subject_type="user",
            subject_id=user["id"],
            ip_address=None,
            user_agent=None,
            details={"username": user["username"], "role": role["name"]},
            redis_client_override=self.blacklist.client,
        )

        return {
            "id": user["id"],
            "username": user["username"],
            "role": role["name"],
            "tenant_id": user.get("tenant_id"),
        }

    async def list_roles(self) -> list[dict]:
        return await self.repo.list_roles()

    async def get_current_user(self, user_id: str) -> dict:
        """Get current user info with role. Raises ValueError if not found."""
        user = await self.repo.get_user_by_id(user_id)
        if user is None:
            raise ValueError("User not found")
        role = await self.repo.get_role_by_id(user["role_id"])
        return {
            "user_id": user["id"],
            "username": user["username"],
            "role": role["name"] if role else "unknown",
            "tenant_id": user.get("tenant_id"),
            "is_active": user["is_active"],
        }

    async def list_users(self) -> list[dict]:
        return await self.repo.list_users_with_roles()

    async def delete_user(self, *, username: str, admin_user_id: str) -> dict:
        """Delete a user by username. Raises on not found or self-delete."""
        normalized = username.strip()
        user = await self.repo.get_user_by_username(normalized)
        if user is None:
            raise ValueError("User not found")

        # Prevent self-deletion
        if user["id"] == admin_user_id:
            raise ValueError("Cannot delete your own account")

        await self.repo.delete_user(user["id"])

        safe_record_audit(
            action="auth.user.delete",
            actor_user_id=admin_user_id,
            subject_type="user",
            subject_id=user["id"],
            ip_address=None,
            user_agent=None,
            details={"username": user["username"]},
            redis_client_override=self.blacklist.client,
        )

        return {"status": "deleted", "username": user["username"]}
