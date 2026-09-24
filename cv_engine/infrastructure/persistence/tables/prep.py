"""CV-preparation tables: snapshot -> analysis -> selection -> draft -> approval."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._helpers import IsoTimestamp, sequence_column
from ._metadata import metadata

job_snapshots = Table(
    "job_snapshots",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("payload_path", Text, nullable=False),
    Column("source_hash", Text, nullable=False),
    Column("normalized_hash", Text, nullable=False),
    Column("source_url", Text),
    Column("captured_at", IsoTimestamp(), nullable=False),
    Column("source_metadata_json", JSONB, nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
    UniqueConstraint("application_id", "source_hash"),
    UniqueConstraint("application_id", "id"),
)

job_analyses = Table(
    "job_analyses",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("job_snapshot_id", UUID(as_uuid=False), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("structured_json", JSONB, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
    UniqueConstraint("application_id", "id"),
    ForeignKeyConstraint(
        ("application_id", "job_snapshot_id"),
        ("job_snapshots.application_id", "job_snapshots.id"),
    ),
)

selection_plans = Table(
    "selection_plans",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("job_analysis_id", UUID(as_uuid=False), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("plan_json", JSONB, nullable=False),
    Column("candidate_context_version", Text, nullable=False),
    Column("candidate_context_hash", Text, nullable=False),
    Column("profile_version", Text, nullable=False),
    Column("selection_policy_version", Text, nullable=False),
    Column("track_emphasis_dependencies_json", JSONB, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
    UniqueConstraint("application_id", "id"),
    UniqueConstraint("id", "job_analysis_id"),
    ForeignKeyConstraint(
        ("application_id", "job_analysis_id"),
        ("job_analyses.application_id", "job_analyses.id"),
    ),
)

working_drafts = Table(
    "working_drafts",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("job_analysis_id", UUID(as_uuid=False), ForeignKey("job_analyses.id"), nullable=False),
    Column("selection_plan_id", UUID(as_uuid=False), nullable=False),
    Column(
        "parent_revision_id",
        UUID(as_uuid=False),
        ForeignKey(
            "approved_revisions.id",
            name="fk_working_drafts_parent_revision_id_approved_revisions",
            use_alter=True,
        ),
    ),
    Column("source_json", JSONB, nullable=False),
    Column("edit_version", Integer, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("active", Boolean, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("updated_at", IsoTimestamp(), nullable=False),
    CheckConstraint("edit_version > 0", name="edit_version_positive"),
    ForeignKeyConstraint(
        ("application_id", "selection_plan_id"),
        ("selection_plans.application_id", "selection_plans.id"),
    ),
    ForeignKeyConstraint(
        ("selection_plan_id", "job_analysis_id"),
        ("selection_plans.id", "selection_plans.job_analysis_id"),
    ),
)
Index(
    "one_active_working_draft_per_application",
    working_drafts.c.application_id,
    unique=True,
    postgresql_where=working_drafts.c.active.is_(True),
)

approved_revisions = Table(
    "approved_revisions",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("job_snapshot_id", UUID(as_uuid=False), ForeignKey("job_snapshots.id"), nullable=False),
    Column("job_analysis_id", UUID(as_uuid=False), ForeignKey("job_analyses.id"), nullable=False),
    Column(
        "selection_plan_id", UUID(as_uuid=False), ForeignKey("selection_plans.id"), nullable=False
    ),
    Column(
        "working_draft_id", UUID(as_uuid=False), ForeignKey("working_drafts.id"), nullable=False
    ),
    Column("draft_edit_version", Integer, nullable=False),
    Column("draft_content_hash", Text, nullable=False),
    Column("resume_json_path", Text, nullable=False, unique=True),
    Column("resume_json_hash", Text, nullable=False),
    Column("resume_markdown_path", Text, nullable=False, unique=True),
    Column("resume_markdown_hash", Text, nullable=False),
    Column("candidate_context_version", Text, nullable=False),
    Column("candidate_context_hash", Text, nullable=False),
    Column("facts_version", Text, nullable=False),
    Column("knowledge_context_hash", Text, nullable=False),
    Column("profile_version", Text, nullable=False),
    Column("selection_policy_version", Text, nullable=False),
    Column("track_emphasis_dependencies_json", JSONB, nullable=False),
    Column(
        "validation_run_id",
        UUID(as_uuid=False),
        ForeignKey(
            "validation_runs.id",
            name="fk_approved_revisions_validation_run_id_validation_runs",
            use_alter=True,
        ),
        nullable=False,
        unique=True,
    ),
    Column("validator_versions_json", JSONB, nullable=False),
    Column("decision_provenance_json", JSONB, nullable=False),
    Column("approved_at", IsoTimestamp(), nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    CheckConstraint("draft_edit_version > 0", name="draft_edit_version_positive"),
    UniqueConstraint("application_id", "version_number"),
)

decision_records = Table(
    "decision_records",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column(
        "approved_revision_id",
        UUID(as_uuid=False),
        ForeignKey("approved_revisions.id"),
        nullable=False,
        unique=True,
    ),
    Column("structured_json", JSONB, nullable=False),
    Column("summary", Text, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
)

validation_runs = Table(
    "validation_runs",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    sequence_column("validation_runs"),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("artifact_version_id", UUID(as_uuid=False), ForeignKey("artifact_versions.id")),
    Column("phase", Text, nullable=False),
    Column("report_json", JSONB, nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("working_draft_id", UUID(as_uuid=False), ForeignKey("working_drafts.id")),
    Column("edit_version", Integer),
    Column("content_hash", Text),
    Column("job_snapshot_id", UUID(as_uuid=False), ForeignKey("job_snapshots.id")),
    Column("job_analysis_id", UUID(as_uuid=False), ForeignKey("job_analyses.id")),
    Column("selection_plan_id", UUID(as_uuid=False), ForeignKey("selection_plans.id")),
    Column("knowledge_context_hash", Text),
    Column("validator_versions_json", JSONB),
    CheckConstraint("edit_version IS NULL OR edit_version > 0", name="edit_version_positive"),
)
Index(
    "idx_validation_runs_draft",
    validation_runs.c.working_draft_id,
    validation_runs.c.created_at.desc(),
    validation_runs.c.seq.desc(),
)
Index(
    "idx_validation_runs_artifact",
    validation_runs.c.artifact_version_id,
    validation_runs.c.phase,
    validation_runs.c.created_at.desc(),
)
