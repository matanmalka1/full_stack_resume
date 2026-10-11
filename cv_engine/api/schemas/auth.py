from __future__ import annotations

from .health import HttpSchema


class LoginRequest(HttpSchema):
    email: str
    password: str


class ChangePasswordRequest(HttpSchema):
    current_password: str
    new_password: str


class MeResponse(HttpSchema):
    id: str
    email: str
    created_at: str
