from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, User
from app.utils.datetime_utils import to_vietnam_iso


class AuthRepository:
    """Data access layer for User and Role models."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_username(self, username: str, include_hash: bool = False) -> dict | None:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._user_to_dict(row) if include_hash else self._user_to_dict_safe(row)

    async def get_user_by_id(self, user_id: str, include_hash: bool = False) -> dict | None:
        row = await self.session.get(User, user_id)
        if row is None:
            return None
        return self._user_to_dict(row) if include_hash else self._user_to_dict_safe(row)

    async def create_user(self, *, username: str, password_hash: str, role_id: str, commit: bool = True) -> dict:
        user = User(username=username, password_hash=password_hash, role_id=role_id)
        self.session.add(user)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(user)
        return self._user_to_dict(user)

    async def create_user_with_tenant(
        self, *, username: str, password_hash: str, role_id: str, tenant_id: str | None, commit: bool = True
    ) -> dict:
        user = User(username=username, password_hash=password_hash, role_id=role_id, tenant_id=tenant_id)
        self.session.add(user)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(user)
        return self._user_to_dict(user)

    async def update_user(self, user_id: str, updates: dict, commit: bool = True) -> dict | None:
        user = await self.session.get(User, user_id)
        if user is None:
            return None
        
        for key, value in updates.items():
            setattr(user, key, value)
            
        if commit:
            await self.session.commit()
            await self.session.refresh(user)
        else:
            await self.session.flush()
            
        return self._user_to_dict(user)

    async def delete_user(self, user_id: str) -> bool:
        user = await self.session.get(User, user_id)
        if user is None:
            return False
        await self.session.delete(user)
        await self.session.commit()
        return True

    async def get_role_by_name(self, name: str) -> dict | None:
        stmt = select(Role).where(Role.name == name)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._role_to_dict(row) if row else None

    async def get_role_by_id(self, role_id: str) -> dict | None:
        row = await self.session.get(Role, role_id)
        return self._role_to_dict(row) if row else None

    async def list_roles(self) -> list[dict]:
        stmt = select(Role).order_by(Role.name.asc())
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._role_to_dict(r) for r in rows]

    async def list_users_with_roles(self) -> list[dict]:
        stmt = select(User, Role).join(Role, User.role_id == Role.id)
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "id": str(u.id),
                "username": u.username,
                "role": r.name,
                "role_id": str(r.id),
                "tenant_id": str(u.tenant_id) if u.tenant_id else None,
                "is_active": u.is_active,
            }
            for u, r in rows
        ]

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _user_to_dict(user: User) -> dict:
        return {
            "id": str(user.id),
            "username": user.username,
            "password_hash": user.password_hash,
            "role_id": str(user.role_id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "is_active": user.is_active,
            "created_at": to_vietnam_iso(user.created_at),
            "updated_at": to_vietnam_iso(user.updated_at),
        }

    @staticmethod
    def _user_to_dict_safe(user: User) -> dict:
        return {
            "id": str(user.id),
            "username": user.username,
            "role_id": str(user.role_id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "is_active": user.is_active,
            "created_at": to_vietnam_iso(user.created_at),
            "updated_at": to_vietnam_iso(user.updated_at),
        }

    @staticmethod
    def _role_to_dict(role: Role) -> dict:
        return {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
        }
