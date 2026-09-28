"""drop idempotency receipts

Approval stopped using idempotency receipts with the single-document model (decision 4),
and the draft-replacement Operation that also wrote them is gone. Nothing reads or writes
the table, so it is dropped with its completion guard. Its row triggers go with it.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-28 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("idempotency_receipts")
    op.execute("DROP FUNCTION cv_guard_idempotency_receipt_completion()")


def downgrade() -> None:
    raise NotImplementedError(
        "0003 drops a table nothing writes; recreate the database from 0001 instead."
    )
