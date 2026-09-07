"""CV-preparation tables: snapshot -> analysis -> selection -> draft -> approval."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from ._helpers import sequence_column
from ._metadata import metadata

job_snapshots = Table(
    "job_snapshots",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("payload_path", Text, nullable=False),
    Column("source_hash", Text, nullable=False),
    Column("normalized_hash", Text, nullable=False),
    Column("source_url", Text),
    Column("captured_at", Text, nullable=False),
    Column("source_metadata_json", JSONB, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("prior_snapshot_id", String, ForeignKey("job_snapshots.id")),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
    UniqueConstraint("application_id", "content_hash"),
)
Index("idx_snapshots_application", job_snapshots.c.application_id)

job_analyses = Table(
    "job_analyses",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("job_snapshot_id", String, ForeignKey("job_snapshots.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("structured_json", JSONB, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
)
Index("idx_analyses_application", job_analyses.c.application_id)

selection_plans = Table(
    "selection_plans",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("job_analysis_id", String, ForeignKey("job_analyses.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("plan_json", JSONB, nullable=False),
    Column("candidate_context_version", Text, nullable=False),
    Column("candidate_context_hash", Text, nullable=False),
    Column("profile_version", Text, nullable=False),
    Column("selection_policy_version", Text, nullable=False),
    Column("track_emphasis_dependencies_json", JSONB, nullable=False),
    # A user decision, not an engine one: the manifest inside `plan_json` is
    # what the selection policy decided, and folding acceptance into it would
    # put a human choice inside the engine's own audit record.
    Column("accepted_gaps_json", JSONB, nullable=False, server_default="[]"),
    Column("created_at", Text, nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("application_id", "version_number"),
)

working_drafts = Table(
    "working_drafts",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("job_analysis_id", String, ForeignKey("job_analyses.id"), nullable=False),
    Column("selection_plan_id", String, ForeignKey("selection_plans.id"), nullable=False),
    Column("parent_revision_id", String),
    Column("source_json", JSONB, nullable=False),
    Column("edit_version", Integer, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("active", Boolean, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    CheckConstraint("edit_version > 0", name="edit_version_positive"),
)
Index(
    "one_active_working_draft_per_application",
    working_drafts.c.application_id,
    unique=True,
    postgresql_where=working_drafts.c.active.is_(True),
)

# Written only from draft archive/approval (`services/drafts/archival.py`,
# `approval.py`) - despite the generic-looking name this is a prep-only log,
# not a general per-application event stream. Renamed from `application_events`
# to `draft_lifecycle_events` to say so.
draft_lifecycle_events = Table(
    "draft_lifecycle_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("event_type", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False),
    Column("created_at", Text, nullable=False),
)

approved_revisions = Table(
    "approved_revisions",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("job_snapshot_id", String, ForeignKey("job_snapshots.id"), nullable=False),
    Column("job_analysis_id", String, ForeignKey("job_analyses.id"), nullable=False),
    Column("selection_plan_id", String, ForeignKey("selection_plans.id"), nullable=False),
    Column("working_draft_id", String, ForeignKey("working_drafts.id"), nullable=False),
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
        String,
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
    Column("approved_at", Text, nullable=False),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    CheckConstraint("draft_edit_version > 0", name="draft_edit_version_positive"),
    UniqueConstraint("application_id", "version_number"),
)

decision_records = Table(
    "decision_records",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("artifact_version_id", String, ForeignKey("artifact_versions.id")),
    Column("job_snapshot_id", String, ForeignKey("job_snapshots.id"), nullable=False),
    Column("job_analysis_id", String, ForeignKey("job_analyses.id"), nullable=False),
    Column("structured_json", JSONB, nullable=False),
    Column("summary", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

generation_runs = Table(
    "generation_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("created_at", Text, nullable=False),
    Column("engine_version", Text, nullable=False),
    Column("profile_version", Text, nullable=False),
    Column("rendering_rules_version", Text, nullable=False),
    Column("facts_version", Text, nullable=False),
    Column("ai_provider", Text, nullable=False),
    Column("ai_model", Text, nullable=False),
    Column("task_contract_version", Text, nullable=False),
    Column("prompt_version", Text, nullable=False),
    Column("job_analysis_version", Text, nullable=False),
    Column("instruction_overrides_json", JSONB, nullable=False),
    Column("status", Text, nullable=False),
)

validation_runs = Table(
    "validation_runs",
    metadata,
    Column("id", String, primary_key=True),
    sequence_column("validation_runs"),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("artifact_version_id", String, ForeignKey("artifact_versions.id")),
    Column("phase", Text, nullable=False),
    Column("report_json", JSONB, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("working_draft_id", String, ForeignKey("working_drafts.id")),
    Column("edit_version", Integer),
    Column("content_hash", Text),
    Column("job_snapshot_id", String, ForeignKey("job_snapshots.id")),
    Column("job_analysis_id", String, ForeignKey("job_analyses.id")),
    Column("selection_plan_id", String, ForeignKey("selection_plans.id")),
    Column("knowledge_context_hash", Text),
    Column("validator_versions_json", JSONB),
)
