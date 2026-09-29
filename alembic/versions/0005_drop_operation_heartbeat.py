"""drop operation heartbeat and lease expiry

One worker runs at a time, held by a PostgreSQL advisory lock, and its startup sweep
interrupts every claimed Operation regardless of expiry. Nothing reads a lease expiry or
a heartbeat any more, so both columns go from `operations` and
`operation_resource_leases`, with the CHECK that paired them with `lease_owner`.
`lease_owner` stays: it is who holds a claim, and the running/terminal CHECKs use it.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-29 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_operations_lease_fields"), "operations", type_="check")
    for table in ("operations", "operation_resource_leases"):
        op.drop_column(table, "lease_expires_at")
        op.drop_column(table, "heartbeat_at")


def downgrade() -> None:
    raise NotImplementedError(
        "0005 drops columns nothing reads; recreate the database from 0001 instead."
    )
