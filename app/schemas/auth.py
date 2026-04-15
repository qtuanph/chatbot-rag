from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class LogoutResponse(BaseModel):
    status: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "member"


class CreateUserResponse(BaseModel):
    id: str
    username: str
    role: str
