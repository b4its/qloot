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
    # Self-registration is student-only. Teacher/admin accounts are provisioned
    # by an admin via ``AdminUserCreate`` — never by an anonymous visitor.
    role: str = Field(default="student", pattern="^student$")
    # For students: the class they belong to (e.g. "1A") and programme ("IPA").
    class_code: str | None = Field(default=None, max_length=16)
    class_type: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AdminUserCreate(BaseModel):
    """Admin-driven account creation (may assign any role)."""

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="student", pattern="^(student|teacher|admin)$")
    class_code: str | None = Field(default=None, max_length=16)
    class_type: str | None = Field(default=None, max_length=32)


class RoleOut(ORMModel):
    name: str


class UserOut(ORMModel):
    id: uuid.UUID
    # Output uses a plain string: never re-validate stored data on the way out,
    # otherwise a legacy/reserved-domain email would turn a read into a 500.
    email: str
    full_name: str
    is_active: bool
    chain_user_ref: str
    avatar_url: str | None = None
    created_at: datetime
    last_login_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)
    class_code: str | None = None
    class_type: str | None = None
    # When the current request's session token expires (AUTH-10). Lets the
    # client rotate the token before it lapses instead of being logged out.
    session_expires_at: datetime | None = None


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


class ForgotPasswordOut(BaseModel):
    message: str
    # In non-production environments the raw reset token is returned so the
    # simulated flow can be completed end-to-end without an email server.
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr


class ChangeEmailOut(BaseModel):
    message: str
    change_token: str | None = None


class ConfirmEmailChangeRequest(BaseModel):
    token: str
