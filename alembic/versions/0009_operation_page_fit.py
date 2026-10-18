"""operation page fit: how a new draft was fitted to its page limit

`create_draft` now measures the draft it wrote and, when it runs past the Profile's
page limit, drops lines until it fits. What that step did - and every line it
dropped - is recorded on the succeeded Operation, the way `withheld_claims` records
the lines review withheld. Nullable: every Operation already recorded keeps NULL,
since none of them was fitted; nothing is rewritten.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "operations",
        sa.Column("page_fit", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_operations_page_fit_status"),
        "operations",
        "page_fit IS NULL OR status = 'succeeded'",
    )
    op.create_check_constraint(
        op.f("ck_operations_page_fit_shape"),
        "operations",
        "page_fit IS NULL OR (jsonb_typeof(page_fit) = 'object' AND page_fit ? 'code')",
    )


def downgrade() -> None:
    # Refused while a recorded Operation carries a report: a downgrade never
    # discards what an Operation recorded about the draft it wrote.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM operations WHERE page_fit IS NOT NULL) THEN
            RAISE EXCEPTION 'operations.page_fit holds recorded reports; it is not dropped';
          END IF;
        END; $$;
        """
    )
    op.drop_constraint(op.f("ck_operations_page_fit_shape"), "operations", type_="check")
    op.drop_constraint(op.f("ck_operations_page_fit_status"), "operations", type_="check")
    op.drop_column("operations", "page_fit")
