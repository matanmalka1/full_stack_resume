"""Add safe AI model and reasoning preferences.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("operations", sa.Column("reasoning_effort", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_operations_reasoning_effort"),
        "operations",
        "reasoning_effort IS NULL OR reasoning_effort IN ('low', 'medium', 'high')",
    )
    op.add_column("app_settings", sa.Column("default_ai_model", sa.Text(), nullable=True))
    op.add_column(
        "app_settings",
        sa.Column(
            "default_reasoning_effort",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'medium'"),
        ),
    )
    op.create_check_constraint(
        op.f("ck_app_settings_default_ai_model"),
        "app_settings",
        "default_ai_model IS NULL OR default_ai_model IN "
        "('gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol')",
    )
    op.create_check_constraint(
        op.f("ck_app_settings_default_reasoning_effort"),
        "app_settings",
        "default_reasoning_effort IN ('low', 'medium', 'high')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_app_settings_default_reasoning_effort"),
        "app_settings",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_app_settings_default_ai_model"),
        "app_settings",
        type_="check",
    )
    op.drop_column("app_settings", "default_reasoning_effort")
    op.drop_column("app_settings", "default_ai_model")
    op.drop_constraint(op.f("ck_operations_reasoning_effort"), "operations", type_="check")
    op.drop_column("operations", "reasoning_effort")
