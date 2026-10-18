"""ownership: applications and settings belong to a user

`applications.user_id` makes the Application the owned aggregate root
(architecture §18.3); `user_settings` replaces the singleton `app_settings`; an
Operation's idempotency key is scoped to its Application. An existing installation's
rows are assigned to its one user: the revision refuses when rows exist and the user
count is not exactly one, so the owner is derived from the installation having had one
candidate and nothing is guessed.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUIRE_ONE_OWNER_SQL = """
DO $$
DECLARE user_count integer;
BEGIN
  IF EXISTS (SELECT 1 FROM applications) OR EXISTS (SELECT 1 FROM app_settings) THEN
    SELECT count(*) INTO user_count FROM users;
    IF user_count <> 1 THEN
      RAISE EXCEPTION
        'existing rows need exactly one user to own them, and there are %: run create-user first',
        user_count;
    END IF;
  END IF;
END; $$;
"""

SETTINGS_COLUMNS = (
    "edit_version, auto_generate_when_review_not_required, default_ai_model, "
    "default_reasoning_effort, ui_density, ui_text_size, ui_theme, updated_at"
)


def _settings_columns() -> list[sa.Column]:
    return [
        sa.Column("edit_version", sa.Integer(), nullable=False),
        sa.Column("auto_generate_when_review_not_required", sa.Boolean(), nullable=False),
        sa.Column("default_ai_model", sa.Text(), nullable=True),
        sa.Column(
            "default_reasoning_effort",
            sa.Text(),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
        sa.Column("ui_density", sa.Text(), nullable=False),
        sa.Column("ui_text_size", sa.Text(), nullable=False),
        sa.Column("ui_theme", sa.Text(), server_default=sa.text("'system'"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _settings_checks(table: str) -> list[sa.CheckConstraint]:
    # Spelled as revision 0001 spelled them: a migration never imports the application.
    return [
        sa.CheckConstraint("edit_version > 0", name=op.f(f"ck_{table}_edit_version_positive")),
        sa.CheckConstraint(
            "default_ai_model IS NULL OR default_ai_model IN "
            "('gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol')",
            name=op.f(f"ck_{table}_default_ai_model"),
        ),
        sa.CheckConstraint(
            "default_reasoning_effort IN ('low', 'medium', 'high')",
            name=op.f(f"ck_{table}_default_reasoning_effort"),
        ),
        sa.CheckConstraint(
            "ui_density IN ('comfortable', 'compact')", name=op.f(f"ck_{table}_ui_density")
        ),
        sa.CheckConstraint(
            "ui_text_size IN ('normal', 'large')", name=op.f(f"ck_{table}_ui_text_size")
        ),
        sa.CheckConstraint(
            "ui_theme IN ('system', 'light', 'dark')", name=op.f(f"ck_{table}_ui_theme")
        ),
    ]


def upgrade() -> None:
    op.execute(REQUIRE_ONE_OWNER_SQL)

    op.add_column(
        "applications", sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True)
    )
    op.execute("UPDATE applications SET user_id = (SELECT id FROM users)")
    op.alter_column("applications", "user_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_applications_user_id_users"), "applications", "users", ["user_id"], ["id"]
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])

    op.create_table(
        "user_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        *_settings_columns(),
        *_settings_checks("user_settings"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_settings_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_settings")),
    )
    op.execute(
        f"INSERT INTO user_settings (user_id, {SETTINGS_COLUMNS}) "
        f"SELECT (SELECT id FROM users), {SETTINGS_COLUMNS} FROM app_settings"
    )
    op.drop_table("app_settings")

    op.drop_constraint(
        op.f("uq_operations_operation_type_idempotency_key"), "operations", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_operations_application_id_operation_type_idempotency_key"),
        "operations",
        ["application_id", "operation_type", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_operations_application_id_operation_type_idempotency_key"),
        "operations",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_operations_operation_type_idempotency_key"),
        "operations",
        ["operation_type", "idempotency_key"],
    )

    op.create_table(
        "app_settings",
        sa.Column("singleton_id", sa.Integer(), autoincrement=False, nullable=False),
        *_settings_columns(),
        sa.CheckConstraint("singleton_id = 1", name=op.f("ck_app_settings_singleton")),
        *_settings_checks("app_settings"),
        sa.PrimaryKeyConstraint("singleton_id", name=op.f("pk_app_settings")),
    )
    # The one user's row, if any, becomes the singleton again.
    op.execute(
        f"INSERT INTO app_settings (singleton_id, {SETTINGS_COLUMNS}) "
        f"SELECT 1, {SETTINGS_COLUMNS} FROM user_settings LIMIT 1"
    )
    op.drop_table("user_settings")

    op.drop_index("ix_applications_user_id", table_name="applications")
    op.drop_constraint(op.f("fk_applications_user_id_users"), "applications", type_="foreignkey")
    op.drop_column("applications", "user_id")
