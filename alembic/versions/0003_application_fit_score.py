"""add applications.fit_score, the numeric fit measure fit_level is read off

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("fit_score", sa.Float(), nullable=True))
    op.create_check_constraint(
        "fit_score",
        "applications",
        "fit_score IS NULL OR (fit_score >= 0 AND fit_score <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint("fit_score", "applications", type_="check")
    op.drop_column("applications", "fit_score")
