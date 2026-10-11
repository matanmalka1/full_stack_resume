"""Stateless token adapter for users and their sessions."""

from __future__ import annotations

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from ...application.accounts import ActiveSession, StoredUser
from ...application.errors import StateConflict
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from .connection import SqlAlchemyTransactionManager
from .tables import rate_limit_buckets, user_sessions, users


def _user(row) -> StoredUser:
    return StoredUser(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


class SqlAlchemyAccountRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def insert_user(
        self,
        tx: WriteTransaction,
        *,
        user_id: str,
        email: str,
        password_hash: str,
        created_at: str,
    ) -> StoredUser:
        connection = self._transactions.connection_for(tx, access="write")
        try:
            # A savepoint, so the refusal leaves the caller's transaction usable.
            with connection.begin_nested():
                connection.execute(
                    insert(users).values(
                        id=user_id,
                        email=email,
                        password_hash=password_hash,
                        created_at=created_at,
                    )
                )
        except IntegrityError:
            raise StateConflict("A user with this email already exists.") from None
        return StoredUser(
            id=user_id, email=email, password_hash=password_hash, created_at=created_at
        )

    def user_by_email(self, tx: ReadTransaction, email: str) -> StoredUser | None:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(users).where(users.c.email == email))
            .mappings()
            .one_or_none()
        )
        return None if row is None else _user(row)

    def set_password_hash(self, tx: WriteTransaction, user_id: str, password_hash: str) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            update(users).where(users.c.id == user_id).values(password_hash=password_hash)
        )

    def insert_session(
        self,
        tx: WriteTransaction,
        *,
        session_id: str,
        user_id: str,
        token_hash: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            insert(user_sessions).values(
                id=session_id,
                user_id=user_id,
                token_hash=token_hash,
                created_at=created_at,
                expires_at=expires_at,
            )
        )

    def active_session(
        self, tx: ReadTransaction, token_hash: str, now: str
    ) -> ActiveSession | None:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(user_sessions.c.id.label("session_id"), users)
                .join(users, users.c.id == user_sessions.c.user_id)
                .where(
                    user_sessions.c.token_hash == token_hash,
                    user_sessions.c.revoked_at.is_(None),
                    user_sessions.c.expires_at > now,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return ActiveSession(session_id=row["session_id"], user=_user(row))

    def revoke_sessions(
        self,
        tx: WriteTransaction,
        user_id: str,
        now: str,
        *,
        only_session_id: str | None = None,
    ) -> None:
        statement = update(user_sessions).where(
            user_sessions.c.user_id == user_id, user_sessions.c.revoked_at.is_(None)
        )
        if only_session_id is not None:
            statement = statement.where(user_sessions.c.id == only_session_id)
        self._transactions.connection_for(tx, access="write").execute(
            statement.values(revoked_at=now)
        )

    def release_rate_limit(
        self,
        tx: WriteTransaction,
        *,
        bucket_type: str,
        key_hash: str,
        window_started_at: str,
    ) -> None:
        connection = self._transactions.connection_for(tx, access="write")
        bucket = (
            rate_limit_buckets.c.bucket_type == bucket_type,
            rate_limit_buckets.c.key_hash == key_hash,
            rate_limit_buckets.c.window_started_at == window_started_at,
        )
        # `count > 0` is a constraint, so a last count is a deleted row, not a zero.
        released = connection.execute(
            update(rate_limit_buckets)
            .where(*bucket, rate_limit_buckets.c.count > 1)
            .values(count=rate_limit_buckets.c.count - 1)
        )
        if released.rowcount == 0:
            connection.execute(
                delete(rate_limit_buckets).where(*bucket, rate_limit_buckets.c.count == 1)
            )

    def increment_rate_limit(
        self,
        tx: WriteTransaction,
        *,
        bucket_type: str,
        key_hash: str,
        window_started_at: str,
        updated_at: str,
    ) -> int:
        statement = (
            pg_insert(rate_limit_buckets)
            .values(
                bucket_type=bucket_type,
                key_hash=key_hash,
                window_started_at=window_started_at,
                count=1,
                updated_at=updated_at,
            )
            .on_conflict_do_update(
                index_elements=[
                    rate_limit_buckets.c.bucket_type,
                    rate_limit_buckets.c.key_hash,
                    rate_limit_buckets.c.window_started_at,
                ],
                set_={
                    "count": rate_limit_buckets.c.count + 1,
                    "updated_at": updated_at,
                },
            )
            .returning(rate_limit_buckets.c.count)
        )
        return int(
            self._transactions.connection_for(tx, access="write").execute(statement).scalar_one()
        )

    def delete_rate_limit_windows_before(self, tx: WriteTransaction, before: str) -> int:
        result = self._transactions.connection_for(tx, access="write").execute(
            delete(rate_limit_buckets).where(rate_limit_buckets.c.window_started_at < before)
        )
        return int(result.rowcount or 0)
