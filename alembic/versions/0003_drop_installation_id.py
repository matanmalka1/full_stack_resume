"""drop installation_id

Idempotency was scoped by installation ID + operation type + key. This task is
one user on one machine, so the installation ID was a constant: it repeated the
same value on every row of four tables and distinguished nothing. The effective
scope was already operation type + key, which is now the declared one.

The idempotency-receipt completion guard is recreated without its
`installation_id` equality clause. Every other clause is preserved, so a
completed receipt stays as immutable as before.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("audit_records", "idempotency_receipts", "operations", "recruitment_events")

_RECEIPT_GUARD_WITHOUT_INSTALLATION = """
CREATE OR REPLACE FUNCTION cv_guard_idempotency_receipt_completion() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT (
        OLD.status = 'pending'
        AND NEW.status = 'completed'
        AND OLD.id = NEW.id
        AND OLD.command_type = NEW.command_type
        AND OLD.idempotency_key = NEW.idempotency_key
        AND OLD.payload_json = NEW.payload_json
        AND OLD.payload_hash = NEW.payload_hash
        AND OLD.reserved_entity_id = NEW.reserved_entity_id
        AND OLD.created_at = NEW.created_at
        AND NEW.result_json IS NOT NULL
        AND NEW.completed_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'invalid idempotency receipt update';
    END IF;
    RETURN NEW;
END;
$$;
"""

_RECEIPT_GUARD_WITH_INSTALLATION = """
CREATE OR REPLACE FUNCTION cv_guard_idempotency_receipt_completion() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT (
        OLD.status = 'pending'
        AND NEW.status = 'completed'
        AND OLD.id = NEW.id
        AND OLD.installation_id = NEW.installation_id
        AND OLD.command_type = NEW.command_type
        AND OLD.idempotency_key = NEW.idempotency_key
        AND OLD.payload_json = NEW.payload_json
        AND OLD.payload_hash = NEW.payload_hash
        AND OLD.reserved_entity_id = NEW.reserved_entity_id
        AND OLD.created_at = NEW.created_at
        AND NEW.result_json IS NOT NULL
        AND NEW.completed_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'invalid idempotency receipt update';
    END IF;
    RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    op.execute(sa.text(_RECEIPT_GUARD_WITHOUT_INSTALLATION))

    op.drop_constraint(
        op.f("uq_idempotency_receipts_installation_id_command_type_idempotency_key"),
        "idempotency_receipts",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_idempotency_receipts_command_type_idempotency_key"),
        "idempotency_receipts",
        ["command_type", "idempotency_key"],
    )

    op.drop_constraint(
        op.f("uq_operations_installation_id_operation_type_idempotency_key"),
        "operations",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_operations_operation_type_idempotency_key"),
        "operations",
        ["operation_type", "idempotency_key"],
    )

    for table_name in TABLES:
        op.drop_column(table_name, "installation_id")


def downgrade() -> None:
    for table_name in TABLES:
        op.add_column(
            table_name,
            sa.Column("installation_id", sa.Text(), nullable=False, server_default=""),
        )
        op.alter_column(table_name, "installation_id", server_default=None)

    op.drop_constraint(
        op.f("uq_operations_operation_type_idempotency_key"),
        "operations",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_operations_installation_id_operation_type_idempotency_key"),
        "operations",
        ["installation_id", "operation_type", "idempotency_key"],
    )

    op.drop_constraint(
        op.f("uq_idempotency_receipts_command_type_idempotency_key"),
        "idempotency_receipts",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_idempotency_receipts_installation_id_command_type_idempotency_key"),
        "idempotency_receipts",
        ["installation_id", "command_type", "idempotency_key"],
    )

    op.execute(sa.text(_RECEIPT_GUARD_WITH_INSTALLATION))
