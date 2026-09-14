"""Persist the shared UI theme preference. Existing installations follow the system."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("ui_theme", sa.Text(), nullable=False, server_default=sa.text("'system'")),
    )
    op.create_check_constraint(
        "ui_theme", "app_settings", "ui_theme IN ('system', 'light', 'dark')"
    )


def downgrade() -> None:
    op.drop_constraint("ui_theme", "app_settings", type_="check")
    op.drop_column("app_settings", "ui_theme")
