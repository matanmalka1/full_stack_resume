"""rename workspace settings to application settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("workspace_settings", "app_settings")
    for suffix in (
        "default_execution_mode",
        "ui_density",
        "ui_text_size",
        "edit_version_positive",
        "singleton",
    ):
        op.execute(
            f'ALTER TABLE app_settings RENAME CONSTRAINT '
            f'"ck_workspace_settings_{suffix}" TO "ck_app_settings_{suffix}"'
        )
    op.execute(
        'ALTER TABLE app_settings RENAME CONSTRAINT '
        '"pk_workspace_settings" TO "pk_app_settings"'
    )


def downgrade() -> None:
    for suffix in (
        "default_execution_mode",
        "ui_density",
        "ui_text_size",
        "edit_version_positive",
        "singleton",
    ):
        op.execute(
            f'ALTER TABLE app_settings RENAME CONSTRAINT '
            f'"ck_app_settings_{suffix}" TO "ck_workspace_settings_{suffix}"'
        )
    op.execute(
        'ALTER TABLE app_settings RENAME CONSTRAINT '
        '"pk_app_settings" TO "pk_workspace_settings"'
    )
    op.rename_table("app_settings", "workspace_settings")
