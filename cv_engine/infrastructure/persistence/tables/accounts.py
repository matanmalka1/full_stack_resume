"""Sign-in identity: the users who may sign in and their sessions.

The tables are mutable: a password changes, a session is revoked, and fixed-window
rate-limit counters advance. Cross-user isolation is enforced through owned roots.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, Table, Text
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

rate_limit_buckets = Table(
    "rate_limit_buckets",
    metadata,
    Column("bucket_type", Text, primary_key=True),
    Column("key_hash", Text, primary_key=True),
    Column("window_started_at", IsoTimestamp(), primary_key=True),
    Column("count", Integer, nullable=False),
    Column("updated_at", IsoTimestamp(), nullable=False),
    CheckConstraint("bucket_type IN ('email_failure', 'client_attempt')", name="bucket_type"),
    CheckConstraint("length(key_hash) = 64", name="key_hash_length"),
    CheckConstraint("count > 0", name="count_positive"),
)
Index("ix_rate_limit_buckets_window", rate_limit_buckets.c.window_started_at)
