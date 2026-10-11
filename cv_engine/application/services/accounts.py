"""Accounts, passwords, sessions, and the shared sign-in throttle (product-spec §22).

The session token is 32 random bytes handed to the client once; only its SHA-256 is
stored, so the table never holds anything that signs a request in. Password hashing
runs outside every transaction scope: it is deliberately slow.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from ...domain.accounts import (
    EmailRejected,
    PasswordRejected,
    check_password_policy,
    normalize_email,
)
from ...util import new_id, sha256_text, utc_now
from ..accounts import ActiveSession, SessionGrant, UserView
from ..errors import (
    AuthenticationRequired,
    InvalidCredentials,
    PasswordPolicyFailed,
    PreconditionFailed,
    RateLimited,
    ReauthenticationFailed,
    UnknownRecord,
)
from ..ports.accounts import AccountRepository, PasswordHasher
from ..ports.transactions import TransactionManager, WriteTransaction

DEFAULT_SESSION_DAYS = 30
RATE_LIMIT_WINDOW = timedelta(minutes=15)
EMAIL_FAILURE_LIMIT = 5
CLIENT_ATTEMPT_LIMIT = 20
logger = logging.getLogger(__name__)


def _view(user: UserView) -> UserView:
    return UserView(id=user.id, email=user.email, created_at=user.created_at)


def _token_hash(token: str) -> str:
    return sha256_text(token)


def _checked_password(password: str) -> str:
    try:
        check_password_policy(password)
    except PasswordRejected as error:
        raise PasswordPolicyFailed(str(error)) from None
    return password


class AccountService:
    def __init__(
        self,
        transactions: TransactionManager,
        repository: AccountRepository,
        hasher: PasswordHasher,
        *,
        session_days: int = DEFAULT_SESSION_DAYS,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.transactions = transactions
        self.repo = repository
        self.hasher = hasher
        self.session_days = session_days
        self.clock = clock
        self._dummy_hash: str | None = None

    # Operator commands (architecture §18.7).

    def create_user(self, email: str, password: str) -> UserView:
        try:
            normalized = normalize_email(email)
        except EmailRejected as error:
            raise PreconditionFailed(str(error)) from None
        password_hash = self.hasher.hash(_checked_password(password))
        with self.transactions.write() as tx:
            user = self.repo.insert_user(
                tx,
                user_id=new_id(),
                email=normalized,
                password_hash=password_hash,
                created_at=utc_now(),
            )
        return _view(user)

    def set_password(self, email: str, password: str) -> UserView:
        """Reset a password and end every session of the user."""
        try:
            normalized = normalize_email(email)
        except EmailRejected as error:
            raise PreconditionFailed(str(error)) from None
        password_hash = self.hasher.hash(_checked_password(password))
        with self.transactions.write() as tx:
            user = self.repo.user_by_email(tx, normalized)
            if user is None:
                raise UnknownRecord("No user has this email.")
            self.repo.set_password_hash(tx, user.id, password_hash)
            self.repo.revoke_sessions(tx, user.id, utc_now())
        return _view(user)

    # Web commands (state-and-use-cases.md §23).

    def login(
        self,
        email: str,
        password: str,
        *,
        client_ip: str,
        presented_token: str | None = None,
    ) -> SessionGrant:
        """Sign in with a new session; the session the browser presented, if any, ends.

        The dummy hash is ready before the user is looked up, so the first unknown email
        costs no more than the first wrong password.
        """
        dummy = self._dummy()
        now = self._rate_limit_now()
        email_key = self._email_rate_key(email)
        client_key = sha256_text(f"client:{client_ip}")
        self._reserve_attempt(email_key, client_key, now)
        # The attempt was counted as an email failure when it was reserved, so attempts
        # in flight together cannot each see room under the limit; a sign-in that
        # succeeds gives its count back below.
        try:
            normalized: str | None = normalize_email(email)
        except EmailRejected:
            normalized = None
        user = None
        if normalized is not None:
            with self.transactions.read() as tx:
                user = self.repo.user_by_email(tx, normalized)
        if user is None:
            # Verify anyway, so an unknown email takes as long as a wrong password.
            self.hasher.verify(dummy, password)
            self._log_failed_sign_in()
            raise InvalidCredentials("The email or password is wrong.")
        if not self.hasher.verify(user.password_hash, password):
            self._log_failed_sign_in()
            raise InvalidCredentials("The email or password is wrong.")
        # A hash made with weaker parameters than the library's current defaults is
        # replaced now, while the password is in hand; nothing else could replace it.
        rehashed = (
            self.hasher.hash(password) if self.hasher.needs_rehash(user.password_hash) else None
        )
        with self.transactions.write() as tx:
            self.repo.release_rate_limit(
                tx,
                bucket_type="email_failure",
                key_hash=email_key,
                window_started_at=self._window_start(now).isoformat(),
            )
            if rehashed is not None:
                self.repo.set_password_hash(tx, user.id, rehashed)
            if presented_token:
                previous = self.repo.active_session(tx, _token_hash(presented_token), utc_now())
                if previous is not None:
                    self.repo.revoke_sessions(
                        tx, previous.user.id, utc_now(), only_session_id=previous.session_id
                    )
            return self._new_session(tx, user)

    def cleanup_rate_limits(self) -> int:
        """Remove completed fixed windows; the worker owns periodic cleanup."""
        current_window = self._window_start(self._rate_limit_now()).isoformat()
        with self.transactions.write() as tx:
            return self.repo.delete_rate_limit_windows_before(tx, current_window)

    def _reserve_attempt(self, email_key: str, client_key: str, now: datetime) -> None:
        """Count the attempt against both limits in one atomic step per bucket.

        Each increment returns the new count from the same statement, so two attempts
        cannot both read a count under the limit and both proceed. A refusal raises
        inside the scope, which rolls its own increments back.
        """
        window_start = self._window_start(now).isoformat()
        with self.transactions.write() as tx:
            email_failures = self.repo.increment_rate_limit(
                tx,
                bucket_type="email_failure",
                key_hash=email_key,
                window_started_at=window_start,
                updated_at=now.isoformat(),
            )
            if email_failures > EMAIL_FAILURE_LIMIT:
                raise RateLimited(self._retry_after(now))
            client_attempts = self.repo.increment_rate_limit(
                tx,
                bucket_type="client_attempt",
                key_hash=client_key,
                window_started_at=window_start,
                updated_at=now.isoformat(),
            )
            if client_attempts > CLIENT_ATTEMPT_LIMIT:
                raise RateLimited(self._retry_after(now))

    @staticmethod
    def _window_start(now: datetime) -> datetime:
        normalized = now.astimezone(UTC)
        minute = normalized.minute - normalized.minute % 15
        return normalized.replace(minute=minute, second=0, microsecond=0)

    @classmethod
    def _retry_after(cls, now: datetime) -> int:
        remaining = cls._window_start(now) + RATE_LIMIT_WINDOW - now.astimezone(UTC)
        return max(1, int(remaining.total_seconds() + 0.999999))

    @staticmethod
    def _email_rate_key(email: str) -> str:
        # Invalid addresses still need a stable bucket, without being persisted raw.
        try:
            value = normalize_email(email)
        except EmailRejected:
            value = email.strip().lower()
        return sha256_text(f"email:{value}")

    def _rate_limit_now(self) -> datetime:
        now = self.clock()
        return now if now.tzinfo is not None else now.replace(tzinfo=UTC)

    def current_user(self, token: str | None) -> UserView:
        return _view(self._session(token).user)

    def logout(self, token: str | None) -> None:
        """End this session. Without a live one there is nothing to end, which is not an error:
        the reader asked to leave, and the cookie is cleared either way."""
        try:
            session = self._session(token)
        except AuthenticationRequired:
            return
        with self.transactions.write() as tx:
            self.repo.revoke_sessions(
                tx, session.user.id, utc_now(), only_session_id=session.session_id
            )

    def logout_all(self, token: str | None) -> None:
        session = self._session(token)
        with self.transactions.write() as tx:
            self.repo.revoke_sessions(tx, session.user.id, utc_now())

    def change_password(
        self, token: str | None, current_password: str, new_password: str
    ) -> SessionGrant:
        """End every other session and rotate the current one."""
        session = self._session(token)
        if not self.hasher.verify(session.user.password_hash, current_password):
            raise ReauthenticationFailed("The current password is wrong.")
        password_hash = self.hasher.hash(_checked_password(new_password))
        with self.transactions.write() as tx:
            self.repo.set_password_hash(tx, session.user.id, password_hash)
            self.repo.revoke_sessions(tx, session.user.id, utc_now())
            return self._new_session(tx, session.user)

    def _session(self, token: str | None) -> ActiveSession:
        if not token:
            raise AuthenticationRequired("Sign in to continue.")
        with self.transactions.read() as tx:
            session = self.repo.active_session(tx, _token_hash(token), utc_now())
        if session is None:
            raise AuthenticationRequired("Sign in to continue.")
        return session

    def _new_session(self, tx: WriteTransaction, user: UserView) -> SessionGrant:
        token = secrets.token_urlsafe(32)
        created_at = utc_now()
        expires_at = (
            datetime.fromisoformat(created_at) + timedelta(days=self.session_days)
        ).isoformat()
        self.repo.insert_session(
            tx,
            session_id=new_id(),
            user_id=user.id,
            token_hash=_token_hash(token),
            created_at=created_at,
            expires_at=expires_at,
        )
        return SessionGrant(token=token, expires_at=expires_at, user=_view(user))

    def _dummy(self) -> str:
        if self._dummy_hash is None:
            self._dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        return self._dummy_hash

    @staticmethod
    def _log_failed_sign_in() -> None:
        # Neither the email nor the password: a failed sign-in is a fact, not evidence.
        logger.warning("sign-in failed")
