"""Repository for User and Role data access."""

from __future__ import annotations


from sqlalchemy.orm import Session

from app.models.auth import Role, User


class AuthRepository:
    """Data access layer for User and Role models."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_by_username(self, username: str, include_hash: bool = False) -> dict | None:
        row = self.session.query(User).filter(User.username == username).one_or_none()
        if row is None:
            return None
        return self._user_to_dict(row) if include_hash else self._user_to_dict_safe(row)

    def get_user_by_id(self, user_id: str, include_hash: bool = False) -> dict | None:
        row = self.session.get(User, user_id)
        if row is None:
            return None
        return self._user_to_dict(row) if include_hash else self._user_to_dict_safe(row)

    def create_user(self, *, username: str, password_hash: str, role_id: str) -> dict:
        user = User(username=username, password_hash=password_hash, role_id=role_id)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return self._user_to_dict(user)

    def delete_user(self, user_id: str) -> bool:
        user = self.session.get(User, user_id)
        if user is None:
            return False
        self.session.delete(user)
        self.session.commit()
        return True

    def get_role_by_name(self, name: str) -> dict | None:
        row = self.session.query(Role).filter(Role.name == name).one_or_none()
        return self._role_to_dict(row) if row else None

    def get_role_by_id(self, role_id: str) -> dict | None:
        row = self.session.get(Role, role_id)
        return self._role_to_dict(row) if row else None

    def list_roles(self) -> list[dict]:
        rows = self.session.query(Role).order_by(Role.name.asc()).all()
        return [self._role_to_dict(r) for r in rows]

    def list_users_with_roles(self) -> list[dict]:
        rows = self.session.query(User, Role).join(Role, User.role_id == Role.id).all()
        return [
            {
                "id": str(u.id),
                "username": u.username,
                "role": r.name,
                "role_id": str(r.id),
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
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    @staticmethod
    def _user_to_dict_safe(user: User) -> dict:
        return {
            "id": str(user.id),
            "username": user.username,
            "role_id": str(user.role_id),
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    @staticmethod
    def _role_to_dict(role: Role) -> dict:
        return {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
        }
