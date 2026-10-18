"""document template: the render template a user chose for a CV

Each CV document may name one of the chosen templates (cv_engine/domain/templates.py),
and each user may name a default that a new document starts from. NULL is the
track's own template, which is what every document rendered with before, so every
existing row keeps NULL and its document hash: the hash takes the template in only
when one is set. Nothing is rewritten.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-18 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The names as this revision knows them; a later template is a later revision.
TEMPLATES = (
    "single-column",
    "two-column",
    "modern",
    "modern-two-column",
    "clean",
    "latex",
    "vivid",
    "vivid-single",
    "deedy",
    "modern-deedy",
)
_VALUES = ", ".join(f"'{name}'" for name in TEMPLATES)


def upgrade() -> None:
    op.add_column("cv_documents", sa.Column("template", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_cv_documents_template"),
        "cv_documents",
        f"template IS NULL OR template IN ({_VALUES})",
    )
    op.add_column("user_settings", sa.Column("default_template", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_user_settings_default_template"),
        "user_settings",
        f"default_template IS NULL OR default_template IN ({_VALUES})",
    )


def downgrade() -> None:
    # Refused while a document names a template: its hash includes the name, so
    # dropping the column would leave a hash nothing can reproduce.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM cv_documents WHERE template IS NOT NULL) THEN
            RAISE EXCEPTION 'cv_documents.template is in use; it is not dropped';
          END IF;
        END; $$;
        """
    )
    op.drop_constraint(op.f("ck_user_settings_default_template"), "user_settings", type_="check")
    op.drop_column("user_settings", "default_template")
    op.drop_constraint(op.f("ck_cv_documents_template"), "cv_documents", type_="check")
    op.drop_column("cv_documents", "template")
