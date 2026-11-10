"""drop recruitment tracking: no submissions, recruitment status, or next action

The product no longer records sends or follows an Application through recruitment.
Submissions, recruitment events, the job-text lock that a Submission set, and the
tracking columns on `applications` go together. Submission files already copied to
payload storage are not touched here; nothing references them any more.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-10 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUSES = (
    "'saved', 'applied', 'recruiter_screen', 'interview', 'assignment', "
    "'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed'"
)
_INTERNAL_REFERENCES = (
    "job_text_hash",
    "document_hash",
    "content",
    "html_path",
    "html_sha256",
    "pdf_path",
    "pdf_sha256",
)


def upgrade() -> None:
    op.execute("DROP TRIGGER lock_submitted_job_text ON applications")
    op.execute("DROP FUNCTION cv_guard_submitted_job_text()")
    op.drop_table("submissions")
    op.drop_table("recruitment_events")
    op.execute("DROP SEQUENCE submissions_seq_seq")
    op.execute("DROP SEQUENCE recruitment_events_seq_seq")
    op.drop_index("idx_applications_user_status", table_name="applications")
    op.drop_constraint(op.f("ck_applications_current_status"), "applications", type_="check")
    op.drop_constraint(op.f("ck_applications_terminal_outcome"), "applications", type_="check")
    for column in ("current_status", "next_action", "next_action_date", "terminal_outcome"):
        op.drop_column("applications", column)


def downgrade() -> None:
    # Refused while any Application exists: its status and history are gone, and an
    # Application without its initial recruitment event would be a record that never
    # happened.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM applications) THEN
            RAISE EXCEPTION 'applications exist; their recruitment history cannot be restored';
          END IF;
        END; $$;
        """
    )
    op.add_column("applications", sa.Column("current_status", sa.Text(), nullable=False))
    op.add_column("applications", sa.Column("next_action", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("next_action_date", sa.Date(), nullable=True))
    op.add_column("applications", sa.Column("terminal_outcome", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_applications_current_status"), "applications", f"current_status IN ({_STATUSES})"
    )
    op.create_check_constraint(
        op.f("ck_applications_terminal_outcome"),
        "applications",
        "terminal_outcome IS NULL OR terminal_outcome IN ('accepted', 'rejected', 'withdrawn')",
    )
    op.create_index("idx_applications_user_status", "applications", ["user_id", "current_status"])
    op.execute(sa.schema.CreateSequence(sa.Sequence("recruitment_events_seq_seq")))
    op.execute(sa.schema.CreateSequence(sa.Sequence("submissions_seq_seq")))
    op.create_table(
        "recruitment_events",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "seq",
            sa.BigInteger(),
            server_default=sa.text("nextval('recruitment_events_seq_seq')"),
            nullable=False,
        ),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("corrects_event_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("client", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')", name=op.f("ck_recruitment_events_actor_type")
        ),
        sa.CheckConstraint(
            "client IN ('web', 'worker')", name=op.f("ck_recruitment_events_client")
        ),
        sa.CheckConstraint(
            "event_type != 'status_correction' OR "
            "(corrects_event_id IS NOT NULL AND length(trim(reason)) > 0)",
            name=op.f("ck_recruitment_events_correction_reason"),
        ),
        sa.CheckConstraint(
            "event_type = 'status_correction' OR corrects_event_id IS NULL",
            name=op.f("ck_recruitment_events_correction_reference"),
        ),
        sa.CheckConstraint(
            "event_type IN ('status_transition', 'status_correction', 'next_action')",
            name=op.f("ck_recruitment_events_event_type"),
        ),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({_STATUSES})",
            name=op.f("ck_recruitment_events_from_status"),
        ),
        sa.CheckConstraint(
            f"to_status IS NULL OR to_status IN ({_STATUSES})",
            name=op.f("ck_recruitment_events_to_status"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_recruitment_events_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["corrects_event_id"],
            ["recruitment_events.id"],
            name=op.f("fk_recruitment_events_corrects_event_id_recruitment_events"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recruitment_events")),
    )
    op.create_index(
        "idx_recruitment_events_application",
        "recruitment_events",
        ["application_id", "occurred_at", "seq"],
        unique=False,
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "seq",
            sa.BigInteger(),
            server_default=sa.text("nextval('submissions_seq_seq')"),
            nullable=False,
        ),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("submission_type", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("job_text_hash", sa.Text(), nullable=True),
        sa.Column("document_hash", sa.Text(), nullable=True),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("html_sha256", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("pdf_sha256", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(submission_type = 'internal' AND "
            + " AND ".join(f"{name} IS NOT NULL" for name in _INTERNAL_REFERENCES)
            + ") OR (submission_type = 'external' AND "
            + " AND ".join(f"{name} IS NULL" for name in _INTERNAL_REFERENCES)
            + ")",
            name=op.f("ck_submissions_references"),
        ),
        sa.CheckConstraint(
            "(job_text_hash IS NULL OR length(job_text_hash) = 64) "
            "AND (document_hash IS NULL OR length(document_hash) = 64) "
            "AND (html_sha256 IS NULL OR length(html_sha256) = 64) "
            "AND (pdf_sha256 IS NULL OR length(pdf_sha256) = 64)",
            name=op.f("ck_submissions_hash_length"),
        ),
        sa.CheckConstraint(
            "submission_type IN ('internal', 'external')",
            name=op.f("ck_submissions_submission_type"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_submissions_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
        sa.UniqueConstraint("html_path", name=op.f("uq_submissions_html_path")),
        sa.UniqueConstraint("pdf_path", name=op.f("uq_submissions_pdf_path")),
    )
    op.create_index(
        "idx_submissions_application",
        "submissions",
        ["application_id", "submitted_at", "seq"],
        unique=False,
    )
    for table_name in ("recruitment_events", "submissions"):
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER no_{operation.lower()}_{table_name} BEFORE {operation} "
                f"ON {table_name} FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change()"
            )
    op.execute(
        """
        CREATE FUNCTION cv_guard_submitted_job_text() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (OLD.job_text, OLD.job_text_hash, OLD.job_normalized_hash, OLD.source_url)
              IS DISTINCT FROM (NEW.job_text, NEW.job_text_hash, NEW.job_normalized_hash, NEW.source_url)
            AND EXISTS (SELECT 1 FROM submissions WHERE submissions.application_id = OLD.id) THEN
            RAISE EXCEPTION 'job text is locked after submission';
          END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER lock_submitted_job_text BEFORE UPDATE ON applications
        FOR EACH ROW EXECUTE FUNCTION cv_guard_submitted_job_text();
        """
    )
