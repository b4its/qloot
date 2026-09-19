"""Auth-related schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    # Students self-register; teacher/admin accounts are created by an admin.
    role: str = Field(default="student", pattern="^(student|teacher)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RoleOut(ORMModel):
    name: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    chain_user_ref: str
    avatar_url: str | None = None
    created_at: datetime
    roles: list[str] = Field(default_factory=list)


class SessionOut(ORMModel):
    id: uuid.UUID
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
