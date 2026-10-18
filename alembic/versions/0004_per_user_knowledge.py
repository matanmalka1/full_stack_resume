"""per-user Knowledge: facts, candidate_contexts, profile_bindings

Written by `python -m cv_engine.admin import-knowledge`; the application keeps reading
Knowledge from files until the revision that switches it over.

A fact is edited in place: `cv_guard_fact_identity`
refuses a change to its identity - `id`, `user_id`, `fact_id`, `source`, `ordinal`,
`created_at` - and `cv_reject_protected_delete` refuses every delete, since deletion is a
status. `replaces` is history only and has no foreign key: imported facts may name v1
ids that exist in no fact source.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FACT_GUARD_SQL = """
CREATE FUNCTION cv_guard_fact_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.id, NEW.user_id, NEW.fact_id, NEW.source, NEW.ordinal, NEW.created_at)
     IS DISTINCT FROM (OLD.id, OLD.user_id, OLD.fact_id, OLD.source, OLD.ordinal, OLD.created_at) THEN
    RAISE EXCEPTION 'immutable fact identity';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER guard_fact_identity BEFORE UPDATE ON facts
  FOR EACH ROW EXECUTE FUNCTION cv_guard_fact_identity();
CREATE TRIGGER prevent_delete_facts BEFORE DELETE ON facts
  FOR EACH ROW EXECUTE FUNCTION cv_reject_protected_delete();
"""


def upgrade() -> None:
    op.create_table(
        "facts",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("fact_id", sa.String(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("renderings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("effective_dates", sa.Text(), nullable=True),
        sa.Column("resume_style", sa.Text(), nullable=False),
        sa.Column("link_target", sa.Text(), nullable=True),
        sa.Column("replaces", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'canonical', 'deleted')", name=op.f("ck_facts_status")
        ),
        sa.CheckConstraint(
            "source IN ('common', 'sales', 'development', 'situational_skills', 'user')",
            name=op.f("ck_facts_source"),
        ),
        sa.CheckConstraint(
            "resume_style IN ('paragraph', 'heading', 'date', 'bullet', 'item', 'contact')",
            name=op.f("ck_facts_resume_style"),
        ),
        sa.CheckConstraint("ordinal > 0", name=op.f("ck_facts_ordinal_positive")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_facts_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facts")),
        sa.UniqueConstraint("user_id", "fact_id", name=op.f("uq_facts_user_id_fact_id")),
        sa.UniqueConstraint(
            "user_id", "source", "ordinal", name=op.f("uq_facts_user_id_source_ordinal")
        ),
    )
    op.create_table(
        "candidate_contexts",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("context_version", sa.Text(), nullable=False),
        sa.Column("name_fact_id", sa.String(), nullable=False),
        sa.Column("filename_name", sa.Text(), nullable=True),
        sa.Column("filename_language", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("contact_fact_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "track_contact_fact_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("link_schemes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fact_store_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "filename_language IN ('en', 'he')",
            name=op.f("ck_candidate_contexts_filename_language"),
        ),
        sa.CheckConstraint(
            "fact_store_version >= 0", name=op.f("ck_candidate_contexts_fact_store_version")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_candidate_contexts_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_candidate_contexts")),
    )
    op.create_table(
        "profile_bindings",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=False),
        sa.Column("binding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("binding_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("binding_version > 0", name=op.f("ck_profile_bindings_binding_version")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_profile_bindings_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", "profile_id", name=op.f("pk_profile_bindings")),
    )
    op.execute(FACT_GUARD_SQL)


def downgrade() -> None:
    op.drop_table("profile_bindings")
    op.drop_table("candidate_contexts")
    op.drop_table("facts")
    op.execute("DROP FUNCTION cv_guard_fact_identity()")
