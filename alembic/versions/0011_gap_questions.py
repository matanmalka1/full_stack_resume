"""gap questions: ask about unmet requirements, draft a pending fact from each answer

Two Operation types (`ask_gap_questions`, `draft_gap_fact`) and their two AI tasks
(`propose_gap_questions`, `draft_fact_from_answer`) join the closed vocabularies, and
two immutable tables record what was asked (`gap_questions`) and what the user did
with each question (`gap_answers`). Both get the shared UPDATE/DELETE guards every
immutable table has. Nothing existing is rewritten.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-28 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OPERATION_TYPES_BEFORE = (
    "analyze_job",
    "create_draft",
    "regenerate_section",
    "regenerate_claim",
    "render_document",
)
_OPERATION_TYPES_AFTER = (*_OPERATION_TYPES_BEFORE, "ask_gap_questions", "draft_gap_fact")
_AI_TASKS_BEFORE = (
    "propose_analysis",
    "draft_resume",
    "assess_claim_support",
    "regenerate_section",
    "regenerate_claim",
)
_AI_TASKS_AFTER = (*_AI_TASKS_BEFORE, "propose_gap_questions", "draft_fact_from_answer")
_IMMUTABLE_TABLES = ("gap_questions", "gap_answers")


def _values(names: tuple[str, ...]) -> str:
    return ", ".join(f"'{name}'" for name in names)


def _replace_checks(operation_types: tuple[str, ...], tasks: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_operations_operation_type"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_operation_type"),
        "operations",
        f"operation_type IN ({_values(operation_types)})",
    )
    op.drop_constraint(op.f("ck_ai_calls_task"), "ai_calls", type_="check")
    op.create_check_constraint(op.f("ck_ai_calls_task"), "ai_calls", f"task IN ({_values(tasks)})")


def upgrade() -> None:
    _replace_checks(_OPERATION_TYPES_AFTER, _AI_TASKS_AFTER)
    op.create_table(
        "gap_questions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("job_analysis_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Text(), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("importance", sa.Text(), nullable=False),
        sa.Column("coverage", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ordinal > 0", name=op.f("ck_gap_questions_ordinal_positive")),
        sa.CheckConstraint(
            "coverage IN ('partial', 'unsupported')", name=op.f("ck_gap_questions_coverage")
        ),
        sa.CheckConstraint(
            "importance IN ('mandatory', 'preferred', 'unknown')",
            name=op.f("ck_gap_questions_importance"),
        ),
        sa.CheckConstraint("language IN ('en', 'he')", name=op.f("ck_gap_questions_language")),
        sa.CheckConstraint(
            "length(trim(question)) > 0", name=op.f("ck_gap_questions_question_nonempty")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_gap_questions_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name=op.f("fk_gap_questions_operation_id_operations"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id", "job_analysis_id"],
            ["job_analyses.application_id", "job_analyses.id"],
            name=op.f("fk_gap_questions_application_id_job_analysis_id_job_analyses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gap_questions")),
        sa.UniqueConstraint(
            "operation_id", "ordinal", name=op.f("uq_gap_questions_operation_id_ordinal")
        ),
        sa.UniqueConstraint(
            "application_id", "id", name=op.f("uq_gap_questions_application_id_id")
        ),
    )
    op.create_table(
        "gap_answers",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("gap_question_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("fact_id", sa.String(), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('answered', 'skipped')", name=op.f("ck_gap_answers_outcome")
        ),
        sa.CheckConstraint(
            "(outcome = 'answered') = "
            "(answer IS NOT NULL AND fact_id IS NOT NULL AND operation_id IS NOT NULL)",
            name=op.f("ck_gap_answers_answered_has_fact"),
        ),
        sa.CheckConstraint(
            "outcome = 'answered' OR (answer IS NULL AND fact_id IS NULL AND operation_id IS NULL)",
            name=op.f("ck_gap_answers_skipped_is_empty"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_gap_answers_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name=op.f("fk_gap_answers_operation_id_operations"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id", "gap_question_id"],
            ["gap_questions.application_id", "gap_questions.id"],
            name=op.f("fk_gap_answers_application_id_gap_question_id_gap_questions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gap_answers")),
        sa.UniqueConstraint("gap_question_id", name=op.f("uq_gap_answers_gap_question_id")),
    )
    for table in _IMMUTABLE_TABLES:
        op.execute(
            f"CREATE TRIGGER no_update_{table} BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change()"
        )
        op.execute(
            f"CREATE TRIGGER no_delete_{table} BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change()"
        )


def downgrade() -> None:
    # Refused while anything was asked or drafted: a downgrade never discards the
    # record of a question or an answer, nor an Operation or AI call of the new kinds.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM gap_questions)
             OR EXISTS (SELECT 1 FROM operations
                        WHERE operation_type IN ('ask_gap_questions', 'draft_gap_fact')) THEN
            RAISE EXCEPTION 'gap questions are on record; they are not dropped';
          END IF;
        END; $$;
        """
    )
    for table in reversed(_IMMUTABLE_TABLES):
        op.drop_table(table)
    _replace_checks(_OPERATION_TYPES_BEFORE, _AI_TASKS_BEFORE)
