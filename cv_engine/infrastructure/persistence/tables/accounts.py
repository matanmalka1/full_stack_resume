"""Sign-in identity: the users who may sign in and their sessions.

Both tables are mutable: a password changes and a session is revoked. Until isolation is
complete the database admits one user (`users_single_user`, architecture §18.1); the
step that completes isolation drops that index in its own revision.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Table, Text, text
from sqlalchemy.dialects.postgresql import UUID

from ._helpers import IsoTimestamp
from ._metadata import metadata

users = Table(
    "users",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("email", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    Index("users_single_user", text("(true)"), unique=True),
)

user_sessions = Table(
    "user_sessions",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("expires_at", IsoTimestamp(), nullable=False),
    Column("revoked_at", IsoTimestamp()),
)
