"""add applications.deleted_at for delete_application soft delete

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `applications` is already a mutable-exception table for the immutability
    # trigger set (product-spec.md invariant #20, architecture.md §6.1), so a
    # nullable soft-delete column here needs no trigger changes. NULL means
    # active; a timestamp means `delete_application` ran.
    op.add_column("applications", sa.Column("deleted_at", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "deleted_at")
