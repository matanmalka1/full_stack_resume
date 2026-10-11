"""drop the retired Knowledge mutation journal

Nothing has written the journal since Knowledge moved into PostgreSQL, and no code
reads it. The revision refuses while the table holds a row, so it never discards
history; it only removes an empty table, its transition guard, and its triggers.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-11 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM knowledge_mutation_journal) THEN
            RAISE EXCEPTION 'knowledge_mutation_journal holds history; it is not dropped';
          END IF;
        END; $$;
        """
    )
    op.drop_index("idx_knowledge_mutation_journal_state", table_name="knowledge_mutation_journal")
    op.drop_table("knowledge_mutation_journal")
    op.execute("DROP FUNCTION cv_guard_knowledge_mutation_transition();")


def downgrade() -> None:
    op.create_table(
        "knowledge_mutation_journal",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("mutation_type", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("staged_reference", sa.Text(), nullable=False),
        sa.Column("old_sha256", sa.Text(), nullable=False),
        sa.Column("new_sha256", sa.Text(), nullable=False),
        sa.Column("db_mutation_type", sa.Text(), nullable=False),
        sa.Column("db_mutation_id", sa.String(), nullable=False),
        sa.Column("db_mutation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recovery_strategy", sa.Text(), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantine_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(state = 'PREPARED' AND committed_at IS NULL AND quarantined_at IS NULL AND quarantine_reason IS NULL) OR (state = 'COMMITTED' AND committed_at IS NOT NULL AND quarantined_at IS NULL AND quarantine_reason IS NULL) OR (state = 'QUARANTINED' AND committed_at IS NULL AND quarantined_at IS NOT NULL AND length(trim(quarantine_reason)) > 0)",
            name=op.f("ck_knowledge_mutation_journal_state_fields"),
        ),
        sa.CheckConstraint(
            "state IN ('PREPARED', 'COMMITTED', 'QUARANTINED')",
            name=op.f("ck_knowledge_mutation_journal_state"),
        ),
        sa.CheckConstraint(
            "length(new_sha256) = 64", name=op.f("ck_knowledge_mutation_journal_new_sha256_length")
        ),
        sa.CheckConstraint(
            "length(old_sha256) = 64", name=op.f("ck_knowledge_mutation_journal_old_sha256_length")
        ),
        sa.CheckConstraint(
            "length(trim(db_mutation_id)) > 0",
            name=op.f("ck_knowledge_mutation_journal_db_mutation_id_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(db_mutation_type)) > 0",
            name=op.f("ck_knowledge_mutation_journal_db_mutation_type_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(mutation_type)) > 0",
            name=op.f("ck_knowledge_mutation_journal_mutation_type_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(recovery_strategy)) > 0",
            name=op.f("ck_knowledge_mutation_journal_recovery_strategy_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(source_reference)) > 0",
            name=op.f("ck_knowledge_mutation_journal_source_reference_nonempty"),
        ),
        sa.CheckConstraint(
            "length(trim(staged_reference)) > 0",
            name=op.f("ck_knowledge_mutation_journal_staged_reference_nonempty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_mutation_journal")),
        sa.UniqueConstraint(
            "db_mutation_type",
            "db_mutation_id",
            name=op.f("uq_knowledge_mutation_journal_db_mutation_type_db_mutation_id"),
        ),
        sa.UniqueConstraint(
            "staged_reference", name=op.f("uq_knowledge_mutation_journal_staged_reference")
        ),
    )
    op.create_index(
        "idx_knowledge_mutation_journal_state",
        "knowledge_mutation_journal",
        ["state", "prepared_at", "id"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION cv_guard_knowledge_mutation_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT (OLD.state = 'PREPARED' AND NEW.state IN ('COMMITTED', 'QUARANTINED')
            AND OLD.id = NEW.id AND OLD.mutation_type = NEW.mutation_type
            AND OLD.source_reference = NEW.source_reference
            AND OLD.staged_reference = NEW.staged_reference
            AND OLD.old_sha256 = NEW.old_sha256 AND OLD.new_sha256 = NEW.new_sha256
            AND OLD.db_mutation_type = NEW.db_mutation_type
            AND OLD.db_mutation_id = NEW.db_mutation_id
            AND OLD.db_mutation_json = NEW.db_mutation_json
            AND OLD.recovery_strategy = NEW.recovery_strategy
            AND OLD.prepared_at = NEW.prepared_at) THEN
            RAISE EXCEPTION 'invalid knowledge mutation transition';
          END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER valid_knowledge_mutation_transition
          BEFORE UPDATE ON knowledge_mutation_journal
          FOR EACH ROW EXECUTE FUNCTION cv_guard_knowledge_mutation_transition();
        CREATE TRIGGER prevent_delete_knowledge_mutation_journal
          BEFORE DELETE ON knowledge_mutation_journal
          FOR EACH ROW EXECUTE FUNCTION cv_reject_protected_delete();
        """
    )
