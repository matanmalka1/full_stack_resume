"""Contracts the account port and the account service both name."""

from __future__ import annotations

from .commands import BoundaryDTO


class UserView(BoundaryDTO):
    """A user as the API and the CLI show it: never the password hash."""

    id: str
    email: str
    created_at: str


class StoredUser(UserView):
    password_hash: str


class SessionGrant(BoundaryDTO):
    """A new session. `token` is the cookie value; only its hash is stored."""

    token: str
    expires_at: str
    user: UserView


class ActiveSession(BoundaryDTO):
    session_id: str
    user: StoredUser
