from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "member"


class CreateUserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
