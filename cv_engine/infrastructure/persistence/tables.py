"""SQLAlchemy Core definitions for the PostgreSQL persistence schema."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Sequence,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

RECRUITMENT_STATUSES = (
    "saved",
    "applied",
    "recruiter_screen",
    "interview",
    "assignment",
    "final_stage",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
    "closed",
)
TERMINAL_OUTCOMES = ("accepted", "rejected", "withdrawn")
OPERATION_TYPES = (
    "analyze_job",
    "propose_selection_plan",
    "create_draft",
    "regenerate_section",
    "regenerate_claim",
    "render_revision",
)
OPERATION_STATUSES = (
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "interrupted",
)
TERMINAL_OPERATION_STATUSES = ("succeeded", "failed", "cancelled", "interrupted")
OPERATION_FAILURE_CODES = (
    "SOURCE_CHANGED",
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_REFUSED",
    "INVALID_OUTPUT",
    "SCHEMA_VIOLATION",
    "RENDER_FAILED",
    "BROWSER_START_FAILED",
    "VALIDATION_EXECUTION_FAILED",
    "CANCELLED_BEFORE_ACTIVATION",
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _sequence_column(table_name: str) -> Column[int]:
    sequence = Sequence(f"{table_name}_seq_seq")
    return Column(
        "seq",
        BigInteger,
        sequence,
        server_default=sequence.next_value(),
        nullable=False,
    )


applications = Table(
    "applications",
    metadata,
    Column("id", String, primary_key=True),
    Column("company", Text, nullable=False),
    Column("target_role", Text, nullable=False),
    Column("normalized_role", Text),
    Column("source_url", Text),
    Column("language", Text),
    Column("track", Text),
    Column("profile", Text),
    Column("emphasis", Text),
    Column("classification_confidence", Float),
    Column("fit_level", Text),
    Column("current_status", Text, nullable=False),
    Column("last_contact_date", Text),
    Column("next_action", Text),
    Column("next_action_date", Text),
    Column("notes", Text, nullable=False, server_default=text("''")),
    Column("source", Text, nullable=False, server_default=text("'manual'")),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("terminal_outcome", Text),
    CheckConstraint("language IN ('en', 'he')", name="language"),
    CheckConstraint(
        f"current_status IN ({_sql_values(RECRUITMENT_STATUSES)})",
        name="current_status",
    ),
    CheckConstraint(
        f"terminal_outcome IS NULL OR terminal_outcome IN ({_sql_values(TERMINAL_OUTCOMES)})",
        name="terminal_outcome",
    ),
)

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

application_events = Table(
    "application_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("event_type", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False),
    Column("created_at", Text, nullable=False),
)

recruitment_events = Table(
    "recruitment_events",
    metadata,
    Column("id", String, primary_key=True),
    _sequence_column("recruitment_events"),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("event_type", Text, nullable=False),
    Column("from_status", Text),
    Column("to_status", Text),
    Column("corrects_event_id", String, ForeignKey("recruitment_events.id")),
    Column("reason", Text, nullable=False, server_default=text("''")),
    Column("actor_type", Text, nullable=False),
    Column("client", Text, nullable=False),
    Column("occurred_at", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", Text, nullable=False),
    CheckConstraint(
        "event_type IN ('status_transition', 'status_correction', 'next_action')",
        name="event_type",
    ),
    CheckConstraint(
        f"from_status IS NULL OR from_status IN ({_sql_values(RECRUITMENT_STATUSES)})",
        name="from_status",
    ),
    CheckConstraint(
        f"to_status IS NULL OR to_status IN ({_sql_values(RECRUITMENT_STATUSES)})",
        name="to_status",
    ),
    CheckConstraint("actor_type IN ('user', 'system')", name="actor_type"),
    CheckConstraint("client IN ('web', 'cli', 'worker')", name="client"),
    CheckConstraint(
        "event_type != 'status_correction' OR "
        "(corrects_event_id IS NOT NULL AND length(trim(reason)) > 0)",
        name="correction_reason",
    ),
    CheckConstraint(
        "event_type = 'status_correction' OR corrects_event_id IS NULL",
        name="correction_reference",
    ),
)
Index(
    "idx_recruitment_events_application",
    recruitment_events.c.application_id,
    recruitment_events.c.occurred_at,
    recruitment_events.c.seq,
)

artifacts = Table(
    "artifacts",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id")),
    Column("artifact_type", Text, nullable=False),
    Column("logical_name", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    UniqueConstraint("application_id", "artifact_type", "logical_name"),
)
Index("idx_artifacts_application", artifacts.c.application_id)

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

artifact_versions = Table(
    "artifact_versions",
    metadata,
    Column("id", String, primary_key=True),
    Column("artifact_id", String, ForeignKey("artifacts.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("lifecycle_status", Text, nullable=False),
    Column("path", Text, nullable=False, unique=True),
    Column("content_hash", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("approved_at", Text),
    Column("submitted_at", Text),
    Column("track", Text),
    Column("profile", Text),
    Column("emphasis", Text),
    Column("facts_version", Text),
    Column("job_snapshot_id", String, ForeignKey("job_snapshots.id")),
    Column("metadata_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("revision_id", String, ForeignKey("approved_revisions.id")),
    CheckConstraint("version_number > 0", name="version_number_positive"),
    UniqueConstraint("artifact_id", "version_number"),
)
Index("idx_versions_artifact", artifact_versions.c.artifact_id)
Index("idx_versions_revision", artifact_versions.c.revision_id)

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
    _sequence_column("validation_runs"),
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

submissions = Table(
    "submissions",
    metadata,
    Column("id", String, primary_key=True),
    _sequence_column("submissions"),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("submission_type", Text, nullable=False),
    Column("approved_revision_id", String, ForeignKey("approved_revisions.id")),
    Column("artifact_version_id", String, ForeignKey("artifact_versions.id"), unique=True),
    Column("submitted_at", Text, nullable=False),
    Column("metadata_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("submission_type IN ('internal', 'external')", name="submission_type"),
    CheckConstraint(
        "(submission_type = 'internal' AND approved_revision_id IS NOT NULL "
        "AND artifact_version_id IS NOT NULL) OR "
        "(submission_type = 'external' AND approved_revision_id IS NULL)",
        name="references",
    ),
)
Index(
    "idx_submissions_application",
    submissions.c.application_id,
    submissions.c.submitted_at,
    submissions.c.seq,
)

audit_records = Table(
    "audit_records",
    metadata,
    Column("id", String, primary_key=True),
    _sequence_column("audit_records"),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("action", Text, nullable=False),
    Column("entity_type", Text, nullable=False),
    Column("entity_id", String, nullable=False),
    Column("actor_type", Text, nullable=False),
    Column("client", Text, nullable=False),
    Column("occurred_at", Text, nullable=False),
    Column("details_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("actor_type IN ('user', 'system')", name="actor_type"),
    CheckConstraint("client IN ('web', 'cli', 'worker')", name="client"),
)
Index(
    "idx_audit_records_application",
    audit_records.c.application_id,
    audit_records.c.occurred_at,
    audit_records.c.seq,
)

fact_events = Table(
    "fact_events",
    metadata,
    Column("id", String, primary_key=True),
    _sequence_column("fact_events"),
    Column("fact_id", String, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("from_status", Text),
    Column("to_status", Text, nullable=False),
    Column("application_id", String, ForeignKey("applications.id")),
    Column("claim_id", String),
    Column("reason", Text, nullable=False, server_default=text("''")),
    Column("fact_json", JSONB, nullable=False),
    Column("fact_hash", Text, nullable=False),
    Column("facts_version", Text, nullable=False),
    Column("lifecycle_version", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)
Index("idx_fact_events_fact", fact_events.c.fact_id)

operations = Table(
    "operations",
    metadata,
    Column("id", String, primary_key=True),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("operation_type", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False),
    Column("payload_hash", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("sources_json", JSONB, nullable=False),
    Column("resources_json", JSONB, nullable=False),
    Column("provider", Text),
    Column("model", Text),
    Column("status", Text, nullable=False),
    Column("phase", Text, nullable=False),
    Column("message", Text, nullable=False, server_default=text("''")),
    Column("created_at", Text, nullable=False),
    Column("started_at", Text),
    Column("finished_at", Text),
    Column("lease_owner", Text),
    Column("lease_expires_at", Text),
    Column("heartbeat_at", Text),
    Column("cancellation_requested_at", Text),
    Column("failure_code", Text),
    Column("safe_failure_detail", Text),
    Column("technical_log_reference", Text),
    Column("retry_of_operation_id", String, ForeignKey("operations.id")),
    Column("attempts_completed", Integer, nullable=False, server_default=text("0")),
    Column("next_attempt_at", Text),
    CheckConstraint(
        f"operation_type IN ({_sql_values(OPERATION_TYPES)})",
        name="operation_type",
    ),
    CheckConstraint("length(payload_hash) = 64", name="payload_hash_length"),
    CheckConstraint("length(trim(idempotency_key)) > 0", name="idempotency_key_nonempty"),
    CheckConstraint(
        f"status IN ({_sql_values(OPERATION_STATUSES)})",
        name="status",
    ),
    CheckConstraint(
        f"failure_code IS NULL OR failure_code IN ({_sql_values(OPERATION_FAILURE_CODES)})",
        name="failure_code",
    ),
    CheckConstraint("attempts_completed >= 0", name="attempts_completed_nonnegative"),
    CheckConstraint(
        "(lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) OR "
        "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL "
        "AND heartbeat_at IS NOT NULL)",
        name="lease_fields",
    ),
    CheckConstraint("status != 'running' OR lease_owner IS NOT NULL", name="running_lease"),
    CheckConstraint(
        "status NOT IN ('succeeded', 'failed', 'cancelled', 'interrupted') OR lease_owner IS NULL",
        name="terminal_lease",
    ),
    CheckConstraint(
        "(status IN ('succeeded', 'failed', 'cancelled', 'interrupted')) = "
        "(finished_at IS NOT NULL)",
        name="terminal_finished_at",
    ),
    CheckConstraint("status != 'failed' OR failure_code IS NOT NULL", name="failed_code"),
    CheckConstraint(
        "failure_code IS NULL OR status IN ('failed', 'cancelled')",
        name="failure_status",
    ),
    CheckConstraint(
        "safe_failure_detail IS NULL OR status IN ('failed', 'cancelled')",
        name="failure_detail_status",
    ),
    UniqueConstraint("operation_type", "idempotency_key"),
)
Index(
    "idx_operations_application_status",
    operations.c.application_id,
    operations.c.status,
    operations.c.created_at,
    operations.c.id,
)
Index(
    "idx_operations_claimable",
    operations.c.status,
    operations.c.next_attempt_at,
    operations.c.created_at,
    operations.c.id,
)

operation_resource_leases = Table(
    "operation_resource_leases",
    metadata,
    Column("resource_kind", Text, nullable=False),
    Column("resource_key", Text, nullable=False),
    Column("slot", Integer, nullable=False),
    Column("operation_id", String, ForeignKey("operations.id"), nullable=False),
    Column("lease_owner", Text, nullable=False),
    Column("lease_expires_at", Text, nullable=False),
    Column("heartbeat_at", Text, nullable=False),
    CheckConstraint(
        "resource_kind IN ('application_mutation', 'render_browser', 'ai')",
        name="resource_kind",
    ),
    CheckConstraint("slot >= 0", name="slot_nonnegative"),
    PrimaryKeyConstraint("resource_kind", "resource_key", "slot"),
    UniqueConstraint("operation_id", "resource_kind", "resource_key"),
)
Index(
    "idx_operation_resource_leases_operation",
    operation_resource_leases.c.operation_id,
)

operation_outputs = Table(
    "operation_outputs",
    metadata,
    Column("id", String, primary_key=True),
    Column("operation_id", String, ForeignKey("operations.id"), nullable=False),
    Column("output_type", Text, nullable=False),
    Column("output_id", String, nullable=False),
    Column("active", Boolean, nullable=False, server_default=false()),
    Column("created_at", Text, nullable=False),
    Column("activated_at", Text),
    CheckConstraint("active = (activated_at IS NOT NULL)", name="active_activation"),
    UniqueConstraint("operation_id", "output_type", "output_id"),
)
Index(
    "idx_operation_outputs_operation",
    operation_outputs.c.operation_id,
    operation_outputs.c.created_at,
    operation_outputs.c.id,
)

idempotency_receipts = Table(
    "idempotency_receipts",
    metadata,
    Column("id", String, primary_key=True),
    Column("command_type", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False),
    Column("payload_hash", Text, nullable=False),
    Column("reserved_entity_id", String, nullable=False),
    Column("status", Text, nullable=False),
    Column("result_json", JSONB),
    Column("created_at", Text, nullable=False),
    Column("completed_at", Text),
    CheckConstraint("length(trim(idempotency_key)) > 0", name="idempotency_key_nonempty"),
    CheckConstraint("length(payload_hash) = 64", name="payload_hash_length"),
    CheckConstraint("status IN ('pending', 'completed')", name="status"),
    CheckConstraint("(status = 'completed') = (result_json IS NOT NULL)", name="result"),
    CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completed_at"),
    UniqueConstraint("command_type", "idempotency_key"),
)

knowledge_mutation_journal = Table(
    "knowledge_mutation_journal",
    metadata,
    Column("id", String, primary_key=True),
    Column("mutation_type", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("source_reference", Text, nullable=False),
    Column("staged_reference", Text, nullable=False, unique=True),
    Column("old_sha256", Text, nullable=False),
    Column("new_sha256", Text, nullable=False),
    Column("db_mutation_type", Text, nullable=False),
    Column("db_mutation_id", String, nullable=False),
    Column("db_mutation_json", JSONB, nullable=False),
    Column("recovery_strategy", Text, nullable=False),
    Column("prepared_at", Text, nullable=False),
    Column("committed_at", Text),
    Column("quarantined_at", Text),
    Column("quarantine_reason", Text),
    CheckConstraint("length(trim(mutation_type)) > 0", name="mutation_type_nonempty"),
    CheckConstraint(
        "state IN ('PREPARED', 'COMMITTED', 'QUARANTINED')",
        name="state",
    ),
    CheckConstraint("length(trim(source_reference)) > 0", name="source_reference_nonempty"),
    CheckConstraint("length(trim(staged_reference)) > 0", name="staged_reference_nonempty"),
    CheckConstraint("length(old_sha256) = 64", name="old_sha256_length"),
    CheckConstraint("length(new_sha256) = 64", name="new_sha256_length"),
    CheckConstraint("length(trim(db_mutation_type)) > 0", name="db_mutation_type_nonempty"),
    CheckConstraint("length(trim(db_mutation_id)) > 0", name="db_mutation_id_nonempty"),
    CheckConstraint("length(trim(recovery_strategy)) > 0", name="recovery_strategy_nonempty"),
    CheckConstraint(
        "(state = 'PREPARED' AND committed_at IS NULL AND quarantined_at IS NULL "
        "AND quarantine_reason IS NULL) OR "
        "(state = 'COMMITTED' AND committed_at IS NOT NULL AND quarantined_at IS NULL "
        "AND quarantine_reason IS NULL) OR "
        "(state = 'QUARANTINED' AND committed_at IS NULL AND quarantined_at IS NOT NULL "
        "AND length(trim(quarantine_reason)) > 0)",
        name="state_fields",
    ),
    UniqueConstraint("db_mutation_type", "db_mutation_id"),
)
Index(
    "idx_knowledge_mutation_journal_state",
    knowledge_mutation_journal.c.state,
    knowledge_mutation_journal.c.prepared_at,
    knowledge_mutation_journal.c.id,
)

workspace_settings = Table(
    "workspace_settings",
    metadata,
    Column("singleton_id", Integer, primary_key=True, autoincrement=False),
    Column("edit_version", Integer, nullable=False),
    Column("auto_generate_when_review_not_required", Boolean, nullable=False),
    Column("ai_enabled_override", Boolean),
    Column("default_execution_mode", Text, nullable=False),
    Column("open_browser_on_launch", Boolean, nullable=False),
    Column("ui_density", Text, nullable=False),
    Column("ui_text_size", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    CheckConstraint("singleton_id = 1", name="singleton"),
    CheckConstraint("edit_version > 0", name="edit_version_positive"),
    CheckConstraint(
        "default_execution_mode IN ('deterministic', 'ai')",
        name="default_execution_mode",
    ),
    CheckConstraint("ui_density IN ('comfortable', 'compact')", name="ui_density"),
    CheckConstraint("ui_text_size IN ('normal', 'large')", name="ui_text_size"),
)

TABLES = tuple(metadata.tables.values())
