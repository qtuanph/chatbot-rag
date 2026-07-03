from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: str | None = None


class LogoutResponse(BaseModel):
    status: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    role: str = Field(default="tenant_admin", min_length=1, max_length=50)
    tenant_id: str | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()


class CreateUserResponse(BaseModel):
    id: str
    username: str
    role: str
    tenant_id: str | None = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str | None = None


class UpdateProfileRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    current_password: str | None = Field(default=None)
    new_password: str | None = Field(default=None, min_length=6, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        return value.strip() if value else None
