"""single cv document

Replaces the revision model with one mutable CV document per Application
(docs/decisions/single-document-model.md). Drops selection_plans, working_drafts,
approved_revisions, decision_records and validation_runs; creates cv_documents;
restructures submissions to carry what was sent; narrows artifacts to provider
responses. The project keeps no data across this change, so it has no downgrade.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INTERNAL_REFERENCES = (
    "job_snapshot_id",
    "document_hash",
    "content",
    "html_path",
    "html_sha256",
    "pdf_path",
    "pdf_sha256",
)


def upgrade() -> None:
    # References into the revision model go first, so the tables can be dropped.
    op.drop_constraint(op.f("ck_submissions_references"), "submissions", type_="check")
    op.drop_constraint(
        op.f("fk_submissions_approved_revision_id_approved_revisions"),
        "submissions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_submissions_artifact_version_id_artifact_versions"),
        "submissions",
        type_="foreignkey",
    )
    op.drop_column("submissions", "approved_revision_id")
    op.drop_column("submissions", "artifact_version_id")
    op.drop_index("idx_versions_revision", table_name="artifact_versions")
    op.drop_constraint(
        op.f("fk_artifact_versions_revision_id_approved_revisions"),
        "artifact_versions",
        type_="foreignkey",
    )
    op.drop_column("artifact_versions", "revision_id")

    # The five tables reference each other in a cycle (working_drafts.parent_revision_id,
    # approved_revisions.validation_run_id), which one DROP statement resolves.
    op.execute(
        "DROP TABLE validation_runs, decision_records, approved_revisions, "
        "working_drafts, selection_plans"
    )
    op.execute(sa.schema.DropSequence(sa.Sequence("validation_runs_seq_seq")))

    op.drop_constraint(
        op.f("ck_artifact_versions_lifecycle_status"), "artifact_versions", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_artifact_versions_lifecycle_status"),
        "artifact_versions",
        "lifecycle_status = 'provider-output'",
    )
    op.create_check_constraint(
        op.f("ck_artifacts_artifact_type"),
        "artifacts",
        "artifact_type = 'provider_response'",
    )

    op.drop_constraint(op.f("ck_operations_operation_type"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_operation_type"),
        "operations",
        "operation_type IN ('analyze_job', 'propose_selection', 'create_draft', "
        "'regenerate_section', 'regenerate_claim', 'render_document')",
    )

    # Mutable by design (state-and-use-cases.md §2), so it gets no immutability triggers.
    op.create_table(
        "cv_documents",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("analysis_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("selection", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("selection_policy_version", sa.Text(), nullable=False),
        sa.Column("document_hash", sa.Text(), nullable=False),
        sa.Column("content_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("checked_basis", sa.Text(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("approved_basis", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rendered_basis", sa.Text(), nullable=True),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("last_render_error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(document_hash) = 64", name=op.f("ck_cv_documents_document_hash_length")
        ),
        sa.CheckConstraint(
            "(checked_basis IS NULL OR length(checked_basis) = 64) "
            "AND (approved_basis IS NULL OR length(approved_basis) = 64) "
            "AND (rendered_basis IS NULL OR length(rendered_basis) = 64)",
            name=op.f("ck_cv_documents_basis_length"),
        ),
        sa.CheckConstraint(
            "(content_report IS NULL) = (checked_basis IS NULL) "
            "AND (checked_basis IS NULL) = (passed IS NULL)",
            name=op.f("ck_cv_documents_check_stamp"),
        ),
        sa.CheckConstraint(
            "(approved_basis IS NULL) = (approved_at IS NULL)",
            name=op.f("ck_cv_documents_approval_stamp"),
        ),
        sa.CheckConstraint(
            "(rendered_basis IS NULL) = (html_path IS NULL) "
            "AND (html_path IS NULL) = (pdf_path IS NULL)",
            name=op.f("ck_cv_documents_render_stamp"),
        ),
        sa.CheckConstraint(
            "content IS NOT NULL OR (checked_basis IS NULL AND approved_basis IS NULL "
            "AND rendered_basis IS NULL AND last_render_error IS NULL)",
            name=op.f("ck_cv_documents_empty_document_unstamped"),
        ),
        sa.CheckConstraint(
            "last_render_error IS NULL OR "
            "(jsonb_typeof(last_render_error) = 'object' AND last_render_error ? 'code')",
            name=op.f("ck_cv_documents_last_render_error_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_cv_documents_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id", "analysis_id"],
            ["job_analyses.application_id", "job_analyses.id"],
            name=op.f("fk_cv_documents_application_id_analysis_id_job_analyses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cv_documents")),
        sa.UniqueConstraint("application_id", name=op.f("uq_cv_documents_application_id")),
        sa.UniqueConstraint("html_path", name=op.f("uq_cv_documents_html_path")),
        sa.UniqueConstraint("pdf_path", name=op.f("uq_cv_documents_pdf_path")),
    )

    op.add_column("submissions", sa.Column("job_snapshot_id", sa.UUID(as_uuid=False)))
    op.add_column("submissions", sa.Column("document_hash", sa.Text()))
    op.add_column("submissions", sa.Column("content", postgresql.JSONB(astext_type=sa.Text())))
    op.add_column("submissions", sa.Column("html_path", sa.Text()))
    op.add_column("submissions", sa.Column("html_sha256", sa.Text()))
    op.add_column("submissions", sa.Column("pdf_path", sa.Text()))
    op.add_column("submissions", sa.Column("pdf_sha256", sa.Text()))
    op.create_unique_constraint(op.f("uq_submissions_html_path"), "submissions", ["html_path"])
    op.create_unique_constraint(op.f("uq_submissions_pdf_path"), "submissions", ["pdf_path"])
    op.create_check_constraint(
        op.f("ck_submissions_references"),
        "submissions",
        "(submission_type = 'internal' AND "
        + " AND ".join(f"{name} IS NOT NULL" for name in INTERNAL_REFERENCES)
        + ") OR (submission_type = 'external' AND "
        + " AND ".join(f"{name} IS NULL" for name in INTERNAL_REFERENCES)
        + ")",
    )
    op.create_check_constraint(
        op.f("ck_submissions_hash_length"),
        "submissions",
        "(document_hash IS NULL OR length(document_hash) = 64) "
        "AND (html_sha256 IS NULL OR length(html_sha256) = 64) "
        "AND (pdf_sha256 IS NULL OR length(pdf_sha256) = 64)",
    )
    op.create_foreign_key(
        op.f("fk_submissions_application_id_job_snapshot_id_job_snapshots"),
        "submissions",
        "job_snapshots",
        ["application_id", "job_snapshot_id"],
        ["application_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    raise NotImplementedError(
        "0002 drops the revision model; there is no data to restore. "
        "Recreate the database from 0001 instead."
    )
