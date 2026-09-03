"""record accepted gaps per gap on the selection plan

A hard gap was cleared by one analysis-level `accepted-low-fit` override, so a
single acceptance dismissed every hard gap at once - including ones the user
had never seen. Acceptance belongs to the SelectionPlan, per gap, with the
actor and time that produced it.

Additive: existing plans default to an empty list, which is what they meant.
`selection_plans` carries the immutability triggers, so acceptance is recorded
by creating a replacement plan version rather than by updating a row.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "selection_plans",
        sa.Column(
            "accepted_gaps_json",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("selection_plans", "accepted_gaps_json")
