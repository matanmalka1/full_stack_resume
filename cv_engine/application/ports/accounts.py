"""Sign-in identity: users and their sessions, one trust boundary."""

from __future__ import annotations

from typing import Protocol

from ..accounts import ActiveSession, StoredUser
from .transactions import ReadTransaction, WriteTransaction


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class AccountRepository(Protocol):
    def insert_user(
        self,
        tx: WriteTransaction,
        *,
        user_id: str,
        email: str,
        password_hash: str,
        created_at: str,
    ) -> StoredUser:
        """Raise `StateConflict` for a taken email or a second user."""
        ...

    def user_by_email(self, tx: ReadTransaction, email: str) -> StoredUser | None: ...

    def set_password_hash(self, tx: WriteTransaction, user_id: str, password_hash: str) -> None: ...

    def insert_session(
        self,
        tx: WriteTransaction,
        *,
        session_id: str,
        user_id: str,
        token_hash: str,
        created_at: str,
        expires_at: str,
    ) -> None: ...

    def active_session(
        self, tx: ReadTransaction, token_hash: str, now: str
    ) -> ActiveSession | None:
        """The unrevoked, unexpired session with this token hash, and its user."""
        ...

    def revoke_sessions(
        self,
        tx: WriteTransaction,
        user_id: str,
        now: str,
        *,
        only_session_id: str | None = None,
    ) -> None:
        """Revoke one session of the user, or every unrevoked one when none is named."""
        ...
