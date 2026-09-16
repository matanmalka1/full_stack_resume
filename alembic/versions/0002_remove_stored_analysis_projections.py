"""remove stored analysis projections and gap acceptances

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_applications_fit_score"), "applications", type_="check")
    op.drop_column("applications", "classification_confidence")
    op.drop_column("applications", "fit_level")
    op.drop_column("applications", "fit_score")
    op.drop_column("selection_plans", "accepted_gaps_json")


def downgrade() -> None:
    op.add_column(
        "selection_plans",
        sa.Column(
            "accepted_gaps_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("applications", sa.Column("fit_score", sa.Float(), nullable=True))
    op.add_column("applications", sa.Column("fit_level", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.create_check_constraint(
        op.f("ck_applications_fit_score"),
        "applications",
        "fit_score IS NULL OR (fit_score >= 0 AND fit_score <= 1)",
    )
