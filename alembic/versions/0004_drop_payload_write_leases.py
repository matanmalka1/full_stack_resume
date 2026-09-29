"""drop payload write leases

Orphan reclaim no longer fences writes through a lease: a payload counts as an orphan
only when no record references it and it was stored longer than `ORPHAN_MIN_AGE` ago
(architecture.md §7.1). Nothing reads or writes the table. It was a mutable exception,
so it carries no immutability triggers.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("payload_write_leases")


def downgrade() -> None:
    raise NotImplementedError(
        "0004 drops a table nothing writes; recreate the database from 0001 instead."
    )
