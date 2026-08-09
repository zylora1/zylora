from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChallengedRequest(StrictModel):
    turnstile_token: str | None = Field(default=None, min_length=1, max_length=2048)


class SignupRequest(ChallengedRequest):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class VerifyEmailRequest(ChallengedRequest):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class EmailRequest(ChallengedRequest):
    email: EmailStr


class LoginRequest(ChallengedRequest):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetConfirmRequest(ChallengedRequest):
    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=12, max_length=128)


class OAuthStartRequest(ChallengedRequest):
    pass


class LogoutAllRequest(StrictModel):
    reason: str = Field(default="USER_REQUEST", min_length=3, max_length=100)


class RevokeSessionRequest(StrictModel):
    reason: str = Field(default="USER_REQUEST", min_length=3, max_length=100)


class AdminLoginRequest(LoginRequest):
    pass


class AuthAcceptedResponse(BaseModel):
    status: Literal["accepted"] = "accepted"


class VerificationRequiredResponse(BaseModel):
    status: Literal["verification_required"] = "verification_required"
    expires_in_seconds: int


class ChallengeConfigResponse(BaseModel):
    enabled: bool
    site_key: str | None


class UserResponse(BaseModel):
    id: UUID
    account_type: Literal["USER", "SUPER_ADMIN"]
    email: str
    status: Literal["PENDING_VERIFICATION", "ACTIVE", "LOCKED", "DELETION_PENDING", "DELETED"]
    verified_at: datetime | None
    locale: str
    timezone: str


class AuthenticatedResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class SessionResponse(BaseModel):
    id: UUID
    audience: Literal["USER_WEB", "ADMIN_WEB"]
    issued_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    device_name: str | None
    current: bool


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class OAuthStartResponse(BaseModel):
    authorization_url: str
