"""Tables that are not owned by prep, tracking, or knowledge alone.

`applications` is the root entity both mechanisms hold a foreign key into, and
it carries prep columns (`track`, `profile`, `emphasis`, `fit_level`, ...) and
tracking columns (`current_status`, `next_action`, ...) side by side on
purpose — see the architecture spec on `applications` as the authoritative
current-state projection paired with append-only event tables. `artifacts`/
`artifact_versions` are prep-produced but `submissions` (tracking) references
`artifact_versions` directly for external-submission attachments, so it is a
genuine shared reference target. `audit_records` is written from both prep and
tracking services. `operations`/its support tables are generic Operation-runner
infrastructure read by the combined query projection (`active_operation`/
`latest_operation` span both domains); every operation type it runs today
happens to be prep-only, but the port/contract is domain-agnostic. `app_settings`
belongs to neither domain.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from ....application.ai_configuration import AI_MODEL_IDS, REASONING_EFFORTS
from ._helpers import sequence_column, sql_values
from ._metadata import metadata

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
    "MISSING_FACT_RENDERING",
    "VALIDATION_EXECUTION_FAILED",
    "CANCELLED_BEFORE_ACTIVATION",
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
        f"current_status IN ({sql_values(RECRUITMENT_STATUSES)})",
        name="current_status",
    ),
    CheckConstraint(
        f"terminal_outcome IS NULL OR terminal_outcome IN ({sql_values(TERMINAL_OUTCOMES)})",
        name="terminal_outcome",
    ),
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

audit_records = Table(
    "audit_records",
    metadata,
    Column("id", String, primary_key=True),
    sequence_column("audit_records"),
    Column("application_id", String, ForeignKey("applications.id"), nullable=False),
    Column("action", Text, nullable=False),
    Column("entity_type", Text, nullable=False),
    Column("entity_id", String, nullable=False),
    Column("actor_type", Text, nullable=False),
    Column("client", Text, nullable=False),
    Column("occurred_at", Text, nullable=False),
    Column("details_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("actor_type IN ('user', 'system')", name="actor_type"),
    CheckConstraint("client IN ('web', 'worker')", name="client"),
)
Index(
    "idx_audit_records_application",
    audit_records.c.application_id,
    audit_records.c.occurred_at,
    audit_records.c.seq,
)

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
    Column("reasoning_effort", Text),
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
        f"operation_type IN ({sql_values(OPERATION_TYPES)})",
        name="operation_type",
    ),
    CheckConstraint("length(payload_hash) = 64", name="payload_hash_length"),
    CheckConstraint(
        f"reasoning_effort IS NULL OR reasoning_effort IN ({sql_values(REASONING_EFFORTS)})",
        name="reasoning_effort",
    ),
    CheckConstraint("length(trim(idempotency_key)) > 0", name="idempotency_key_nonempty"),
    CheckConstraint(
        f"status IN ({sql_values(OPERATION_STATUSES)})",
        name="status",
    ),
    CheckConstraint(
        f"failure_code IS NULL OR failure_code IN ({sql_values(OPERATION_FAILURE_CODES)})",
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

app_settings = Table(
    "app_settings",
    metadata,
    Column("singleton_id", Integer, primary_key=True, autoincrement=False),
    Column("edit_version", Integer, nullable=False),
    Column("auto_generate_when_review_not_required", Boolean, nullable=False),
    Column("ai_enabled_override", Boolean),
    Column("default_execution_mode", Text, nullable=False),
    Column("default_ai_model", Text),
    Column("default_reasoning_effort", Text, nullable=False, server_default=text("'medium'")),
    Column("ui_density", Text, nullable=False),
    Column("ui_text_size", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    CheckConstraint("singleton_id = 1", name="singleton"),
    CheckConstraint("edit_version > 0", name="edit_version_positive"),
    CheckConstraint(
        "default_execution_mode IN ('deterministic', 'ai')",
        name="default_execution_mode",
    ),
    CheckConstraint(
        f"default_ai_model IS NULL OR default_ai_model IN ({sql_values(AI_MODEL_IDS)})",
        name="default_ai_model",
    ),
    CheckConstraint(
        f"default_reasoning_effort IN ({sql_values(REASONING_EFFORTS)})",
        name="default_reasoning_effort",
    ),
    CheckConstraint("ui_density IN ('comfortable', 'compact')", name="ui_density"),
    CheckConstraint("ui_text_size IN ('normal', 'large')", name="ui_text_size"),
)
