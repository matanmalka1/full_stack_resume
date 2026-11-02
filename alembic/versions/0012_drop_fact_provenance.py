"""drop fact provenance: a fact no longer carries a free-text note of where it came from

The note was never read by anything but the facts screen, and what it held was mostly
migration bookkeeping. A gap answer stays on its question with the fact's ID, and a
fact's history stays in `fact_events`, whose stored snapshots are not rewritten.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-02 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("facts", "provenance")


def downgrade() -> None:
    # Refused while any fact exists: its dropped text is gone, and the column is required,
    # so restoring it would mean inventing a value for every row.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM facts) THEN
            RAISE EXCEPTION 'facts exist; their provenance cannot be restored';
          END IF;
        END; $$;
        """
    )
    op.add_column("facts", sa.Column("provenance", sa.Text(), nullable=False))
