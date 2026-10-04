"""Tables that are not owned by prep, tracking, or knowledge alone.

`applications` is the root entity both mechanisms hold a foreign key into, and
it carries prep columns (`track`, `profile`, `emphasis`) and
tracking columns (`current_status`, `next_action`, ...) side by side on
purpose — see the architecture spec on `applications` as the authoritative
current-state projection paired with append-only event tables. `ai_calls` is
the AI call log, one immutable row per provider call attempt of an Operation. `audit_records` is written from both prep and
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
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ....application.ai_configuration import AI_MODEL_IDS, REASONING_EFFORTS
from ....application.operations import STORED_OPERATION_PHASES
from ._helpers import IsoDate, IsoTimestamp, sequence_column, sql_values
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
    "create_draft",
    "regenerate_section",
    "regenerate_claim",
    "render_document",
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
    "PROVIDER_QUOTA_EXHAUSTED",
    "PROVIDER_UNAVAILABLE",
    "PROVIDER_REFUSED",
    "INVALID_OUTPUT",
    "CLAIM_REVIEW_UNCERTAIN",
    "CLAIM_REVIEW_UNSUPPORTED",
    "RENDER_FAILED",
    "BROWSER_START_FAILED",
    "MISSING_FACT_RENDERING",
    "VALIDATION_EXECUTION_FAILED",
    "CANCELLED_BEFORE_ACTIVATION",
    "PROVIDER_NOT_CONFIGURED",
)

applications = Table(
    "applications",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("company", Text, nullable=False),
    Column("target_role", Text, nullable=False),
    Column("normalized_role", Text),
    Column("language", Text),
    Column("track", Text),
    Column("profile", Text),
    Column("emphasis", Text),
    Column("current_status", Text, nullable=False),
    Column("next_action", Text),
    Column("next_action_date", IsoDate()),
    Column("notes", Text, nullable=False, server_default=text("''")),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("updated_at", IsoTimestamp(), nullable=False),
    Column("terminal_outcome", Text),
    # Soft-delete disposition (product-spec.md invariant #20), orthogonal to
    # `current_status`: NULL means active, set means `delete_application` ran.
    # `applications` is already a mutable-exception table, so a nullable
    # column here needs no change to the immutability trigger set.
    Column("deleted_at", IsoTimestamp()),
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

audit_records = Table(
    "audit_records",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    sequence_column("audit_records"),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("action", Text, nullable=False),
    Column("entity_type", Text, nullable=False),
    Column("entity_id", String, nullable=False),
    Column("actor_type", Text, nullable=False),
    Column("client", Text, nullable=False),
    Column("occurred_at", IsoTimestamp(), nullable=False),
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
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("application_id", UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False),
    Column("operation_type", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False),
    Column("payload_hash", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("sources_json", JSONB, nullable=False),
    Column("provider", Text),
    Column("model", Text),
    Column("reasoning_effort", Text),
    Column("status", Text, nullable=False),
    Column("phase", Text, nullable=False),
    Column("message", Text, nullable=False, server_default=text("''")),
    Column("created_at", IsoTimestamp(), nullable=False),
    Column("started_at", IsoTimestamp()),
    Column("finished_at", IsoTimestamp()),
    Column("lease_owner", Text),
    Column("cancellation_requested_at", IsoTimestamp()),
    Column("failure_code", Text),
    Column("safe_failure_detail", Text),
    Column("failure_reason", JSONB),
    # Lines a succeeded writer Operation withheld (each kept its prior wording), with
    # the refused wording and the sources read - the success-side twin of a
    # `claim_review` failure reason.
    Column("withheld_claims", JSONB),
    Column("technical_log_reference", Text),
    Column("retry_of_operation_id", UUID(as_uuid=False), ForeignKey("operations.id")),
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
        f"phase IN ({sql_values(tuple(phase.value for phase in STORED_OPERATION_PHASES))})",
        name="phase",
    ),
    CheckConstraint(
        f"failure_code IS NULL OR failure_code IN ({sql_values(OPERATION_FAILURE_CODES)})",
        name="failure_code",
    ),
    # A claim sets both at once and every exit clears both: the lease is the running
    # runner's fencing token and exists nowhere else.
    CheckConstraint("(status = 'running') = (lease_owner IS NOT NULL)", name="running_lease"),
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
    CheckConstraint(
        "failure_reason IS NULL OR status IN ('failed', 'cancelled')",
        name="failure_reason_status",
    ),
    CheckConstraint(
        "failure_reason IS NULL OR "
        "(jsonb_typeof(failure_reason) = 'object' AND failure_reason ? 'code')",
        name="failure_reason_shape",
    ),
    CheckConstraint(
        "withheld_claims IS NULL OR status = 'succeeded'",
        name="withheld_claims_status",
    ),
    CheckConstraint(
        "withheld_claims IS NULL OR "
        "(jsonb_typeof(withheld_claims) = 'object' AND withheld_claims ? 'code')",
        name="withheld_claims_shape",
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
    operations.c.created_at,
    operations.c.id,
)
# The claim guards (architecture.md §10): the database itself refuses a second running
# Operation for one Application, and a second running render anywhere. A claim that
# loses to either is told apart by the index name (`CLAIM_GUARDS` in
# operation_execution.py).
Index(
    "uq_operations_running_application",
    operations.c.application_id,
    unique=True,
    postgresql_where=text("status = 'running'"),
)
Index(
    "uq_operations_running_render",
    operations.c.operation_type,
    unique=True,
    postgresql_where=text("status = 'running' AND operation_type = 'render_document'"),
)

operation_outputs = Table(
    "operation_outputs",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("operation_id", UUID(as_uuid=False), ForeignKey("operations.id"), nullable=False),
    Column("output_type", Text, nullable=False),
    Column("output_id", UUID(as_uuid=False), nullable=False),
    Column("created_at", IsoTimestamp(), nullable=False),
    UniqueConstraint("operation_id", "output_type", "output_id"),
)
Index(
    "idx_operation_outputs_operation",
    operation_outputs.c.operation_id,
    operation_outputs.c.created_at,
    operation_outputs.c.id,
)

AI_CALL_TASKS = (
    "propose_analysis",
    "draft_resume",
    "assess_claim_support",
    "regenerate_section",
    "regenerate_claim",
)
AI_CALL_OUTCOMES = (
    "succeeded",
    "refused",
    "schema_violation",
    "rate_limited",
    "quota_exhausted",
    "http_error",
    "not_delivered",
    "outcome_unknown",
)

#: The AI call log: one row per provider call attempt, appended as soon as the
#: attempt ends and never changed. Its only lineage is `operation_id`; the
#: Application is the Operation's. `attempt` is the ordinal of the call for its task
#: within the Operation, assigned by the store - how many attempts are allowed is
#: application policy, not a storage invariant.
ai_calls = Table(
    "ai_calls",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("operation_id", UUID(as_uuid=False), ForeignKey("operations.id"), nullable=False),
    Column("task", Text, nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("reasoning_effort", Text),
    Column("task_contract_version", Text, nullable=False),
    Column("input_schema_version", Text, nullable=False),
    Column("input_schema_hash", Text, nullable=False),
    Column("output_schema_version", Text, nullable=False),
    Column("output_schema_hash", Text, nullable=False),
    Column("prompt_version", Text, nullable=False),
    Column("prompt_hash", Text, nullable=False),
    Column("input_hash", Text, nullable=False),
    Column("knowledge_context_hash", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("http_status", Integer),
    Column("error_type", Text),
    Column("error_code", Text),
    Column("retry_after_seconds", Numeric),
    Column("response_id", Text),
    Column("sanitized_response", JSONB),
    Column("sanitized_response_hash", Text),
    Column("output_hash", Text),
    Column("input_tokens", Integer),
    Column("cached_input_tokens", Integer),
    Column("cache_write_tokens", Integer),
    Column("output_tokens", Integer),
    Column("total_tokens", Integer),
    Column("pricing", JSONB),
    Column("cost_usd", Numeric(18, 8)),
    Column("latency_ms", Integer, nullable=False),
    Column("started_at", IsoTimestamp(), nullable=False),
    Column("finished_at", IsoTimestamp(), nullable=False),
    CheckConstraint(f"task IN ({sql_values(AI_CALL_TASKS)})", name="task"),
    CheckConstraint(f"outcome IN ({sql_values(AI_CALL_OUTCOMES)})", name="outcome"),
    CheckConstraint("attempt >= 1", name="attempt_positive"),
    CheckConstraint(
        "retry_after_seconds IS NULL OR retry_after_seconds >= 0",
        name="retry_after_nonnegative",
    ),
    CheckConstraint(
        "sanitized_response IS NULL OR jsonb_typeof(sanitized_response) = 'object'",
        name="sanitized_response_shape",
    ),
    CheckConstraint(
        "(sanitized_response IS NULL) = (sanitized_response_hash IS NULL)",
        name="sanitized_response_hash_present",
    ),
    CheckConstraint(
        "outcome <> 'succeeded' OR (sanitized_response IS NOT NULL AND output_hash IS NOT NULL)",
        name="succeeded_has_output",
    ),
    CheckConstraint(
        "(input_tokens IS NULL OR input_tokens >= 0)"
        " AND (cached_input_tokens IS NULL OR cached_input_tokens >= 0)"
        " AND (cache_write_tokens IS NULL OR cache_write_tokens >= 0)"
        " AND (output_tokens IS NULL OR output_tokens >= 0)"
        " AND (total_tokens IS NULL OR total_tokens >= 0)",
        name="tokens_nonnegative",
    ),
    CheckConstraint(
        "cached_input_tokens IS NULL OR cache_write_tokens IS NULL OR input_tokens IS NULL"
        " OR cached_input_tokens + cache_write_tokens <= input_tokens",
        name="cache_tokens_within_input",
    ),
    CheckConstraint(
        "total_tokens IS NULL OR input_tokens IS NULL OR total_tokens >= input_tokens",
        name="total_covers_input",
    ),
    CheckConstraint(
        "total_tokens IS NULL OR output_tokens IS NULL OR total_tokens >= output_tokens",
        name="total_covers_output",
    ),
    CheckConstraint("cost_usd IS NULL OR cost_usd >= 0", name="cost_nonnegative"),
    CheckConstraint(
        "cost_usd IS NULL OR (input_tokens IS NOT NULL AND output_tokens IS NOT NULL"
        " AND pricing IS NOT NULL)",
        name="cost_has_usage",
    ),
    CheckConstraint("latency_ms >= 0", name="latency_nonnegative"),
    CheckConstraint("finished_at >= started_at", name="finished_after_started"),
    UniqueConstraint("operation_id", "task", "attempt"),
)
Index("idx_ai_calls_operation", ai_calls.c.operation_id, ai_calls.c.started_at, ai_calls.c.id)

app_settings = Table(
    "app_settings",
    metadata,
    Column("singleton_id", Integer, primary_key=True, autoincrement=False),
    Column("edit_version", Integer, nullable=False),
    Column("auto_generate_when_review_not_required", Boolean, nullable=False),
    Column("default_ai_model", Text),
    Column("default_reasoning_effort", Text, nullable=False, server_default=text("'medium'")),
    Column("ui_density", Text, nullable=False),
    Column("ui_text_size", Text, nullable=False),
    Column("ui_theme", Text, nullable=False, server_default=text("'system'")),
    Column("updated_at", IsoTimestamp(), nullable=False),
    CheckConstraint("singleton_id = 1", name="singleton"),
    CheckConstraint("edit_version > 0", name="edit_version_positive"),
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
    CheckConstraint("ui_theme IN ('system', 'light', 'dark')", name="ui_theme"),
)
