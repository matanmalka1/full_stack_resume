"""postgresql baseline

Squashes the former 0001-0005 chain into one baseline: the single-document model
(docs/decisions/single-document-model.md) with no idempotency receipts, payload write
leases, or operation heartbeat/lease expiry.

Revision ID: 0001
Revises:
Create Date: 2026-09-30 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
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

IMMUTABILITY_SQL = """
CREATE FUNCTION cv_reject_immutable_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable record'; END; $$;
CREATE FUNCTION cv_reject_protected_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable record'; END; $$;
DO $$
DECLARE table_name text;
DECLARE missing_exceptions text[];
DECLARE mutable_exceptions constant text[] := ARRAY[
  'applications', 'cv_documents', 'operations', 'operation_resource_leases',
  'operation_outputs', 'knowledge_mutation_journal', 'app_settings'
];
BEGIN
  SELECT array_agg(exception_name ORDER BY exception_name) INTO missing_exceptions
  FROM unnest(mutable_exceptions) AS exception_name
  WHERE NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_tables
    WHERE schemaname = current_schema() AND tablename = exception_name
  );
  IF missing_exceptions IS NOT NULL THEN
    RAISE EXCEPTION 'mutable table exceptions do not exist: %', missing_exceptions;
  END IF;
  FOR table_name IN
    SELECT tablename FROM pg_catalog.pg_tables
    WHERE schemaname = current_schema()
      AND tablename <> 'alembic_version'
      AND tablename <> ALL(mutable_exceptions)
  LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change()', 'no_update_' || table_name, table_name);
    EXECUTE format('CREATE TRIGGER %I BEFORE DELETE ON %I FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change()', 'no_delete_' || table_name, table_name);
  END LOOP;
  FOREACH table_name IN ARRAY ARRAY['operations', 'operation_outputs', 'knowledge_mutation_journal']
  LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE DELETE ON %I FOR EACH ROW EXECUTE FUNCTION cv_reject_protected_delete()', 'prevent_delete_' || table_name, table_name);
  END LOOP;
END; $$;
"""

TRANSITION_GUARDS_SQL = """
CREATE FUNCTION cv_guard_terminal_operation_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('succeeded', 'failed', 'cancelled', 'interrupted') THEN
    RAISE EXCEPTION 'immutable terminal operation';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER prevent_update_terminal_operations BEFORE UPDATE ON operations
FOR EACH ROW EXECUTE FUNCTION cv_guard_terminal_operation_update();

CREATE FUNCTION cv_guard_operation_output_activation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE operation_status text; operation_cancellation_requested_at timestamptz;
BEGIN
  SELECT status, cancellation_requested_at INTO operation_status, operation_cancellation_requested_at
  FROM operations WHERE id = OLD.operation_id;
  IF NOT (OLD.active = FALSE AND NEW.active = TRUE AND NEW.activated_at IS NOT NULL
    AND OLD.id = NEW.id AND OLD.operation_id = NEW.operation_id
    AND OLD.output_type = NEW.output_type AND OLD.output_id = NEW.output_id
    AND OLD.created_at = NEW.created_at AND operation_status = 'running'
    AND operation_cancellation_requested_at IS NULL) THEN
    RAISE EXCEPTION 'invalid operation output update';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER valid_operation_output_activation BEFORE UPDATE ON operation_outputs
FOR EACH ROW EXECUTE FUNCTION cv_guard_operation_output_activation();

CREATE FUNCTION cv_guard_knowledge_mutation_transition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT (OLD.state = 'PREPARED' AND NEW.state IN ('COMMITTED', 'QUARANTINED')
    AND OLD.id = NEW.id AND OLD.mutation_type = NEW.mutation_type
    AND OLD.source_reference = NEW.source_reference AND OLD.staged_reference = NEW.staged_reference
    AND OLD.old_sha256 = NEW.old_sha256 AND OLD.new_sha256 = NEW.new_sha256
    AND OLD.db_mutation_type = NEW.db_mutation_type AND OLD.db_mutation_id = NEW.db_mutation_id
    AND OLD.db_mutation_json = NEW.db_mutation_json AND OLD.recovery_strategy = NEW.recovery_strategy
    AND OLD.prepared_at = NEW.prepared_at) THEN
    RAISE EXCEPTION 'invalid knowledge mutation transition';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER valid_knowledge_mutation_transition BEFORE UPDATE ON knowledge_mutation_journal
FOR EACH ROW EXECUTE FUNCTION cv_guard_knowledge_mutation_transition();
"""


def upgrade() -> None:
    for table_name in (
        "audit_records",
        "fact_events",
        "recruitment_events",
        "submissions",
    ):
        op.execute(sa.schema.CreateSequence(sa.Sequence(f"{table_name}_seq_seq")))
    op.create_table(
        "app_settings",
        sa.Column("singleton_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("edit_version", sa.Integer(), nullable=False),
        sa.Column("auto_generate_when_review_not_required", sa.Boolean(), nullable=False),
        sa.Column("default_ai_model", sa.Text(), nullable=True),
        sa.Column(
            "default_reasoning_effort",
            sa.Text(),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
        sa.Column("ui_density", sa.Text(), nullable=False),
        sa.Column("ui_text_size", sa.Text(), nullable=False),
        sa.Column("ui_theme", sa.Text(), server_default=sa.text("'system'"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "default_ai_model IS NULL OR default_ai_model IN ('gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol')",
            name=op.f("ck_app_settings_default_ai_model"),
        ),
        sa.CheckConstraint(
            "default_reasoning_effort IN ('low', 'medium', 'high')",
            name=op.f("ck_app_settings_default_reasoning_effort"),
        ),
        sa.CheckConstraint(
            "ui_density IN ('comfortable', 'compact')", name=op.f("ck_app_settings_ui_density")
        ),
        sa.CheckConstraint(
            "ui_text_size IN ('normal', 'large')", name=op.f("ck_app_settings_ui_text_size")
        ),
        sa.CheckConstraint(
            "ui_theme IN ('system', 'light', 'dark')", name=op.f("ck_app_settings_ui_theme")
        ),
        sa.CheckConstraint("edit_version > 0", name=op.f("ck_app_settings_edit_version_positive")),
        sa.CheckConstraint("singleton_id = 1", name=op.f("ck_app_settings_singleton")),
        sa.PrimaryKeyConstraint("singleton_id", name=op.f("pk_app_settings")),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("target_role", sa.Text(), nullable=False),
        sa.Column("normalized_role", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("track", sa.Text(), nullable=True),
        sa.Column("profile", sa.Text(), nullable=True),
        sa.Column("emphasis", sa.Text(), nullable=True),
        sa.Column("current_status", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("next_action_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_outcome", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "current_status IN ('saved', 'applied', 'recruiter_screen', 'interview', 'assignment', 'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed')",
            name=op.f("ck_applications_current_status"),
        ),
        sa.CheckConstraint("language IN ('en', 'he')", name=op.f("ck_applications_language")),
        sa.CheckConstraint(
            "terminal_outcome IS NULL OR terminal_outcome IN ('accepted', 'rejected', 'withdrawn')",
            name=op.f("ck_applications_terminal_outcome"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
    )
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
    op.create_table(
        "artifacts",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("logical_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_type = 'provider_response'", name=op.f("ck_artifacts_artifact_type")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_artifacts_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint(
            "application_id",
            "artifact_type",
            "logical_name",
            name=op.f("uq_artifacts_application_id_artifact_type_logical_name"),
        ),
    )
    op.create_table(
        "audit_records",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "seq",
            sa.BigInteger(),
            server_default=sa.text("nextval('audit_records_seq_seq')"),
            nullable=False,
        ),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("client", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')", name=op.f("ck_audit_records_actor_type")
        ),
        sa.CheckConstraint("client IN ('web', 'worker')", name=op.f("ck_audit_records_client")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_audit_records_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_records")),
    )
    op.create_index(
        "idx_audit_records_application",
        "audit_records",
        ["application_id", "occurred_at", "seq"],
        unique=False,
    )
    op.create_table(
        "fact_events",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "seq",
            sa.BigInteger(),
            server_default=sa.text("nextval('fact_events_seq_seq')"),
            nullable=False,
        ),
        sa.Column("fact_id", sa.String(), nullable=False),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("claim_id", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("fact_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fact_hash", sa.Text(), nullable=False),
        sa.Column("facts_version", sa.Text(), nullable=False),
        sa.Column("lifecycle_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_fact_events_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fact_events")),
    )
    op.create_index(
        "idx_fact_events_fact", "fact_events", ["fact_id", "created_at", "seq"], unique=False
    )
    op.create_table(
        "job_snapshots",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("payload_path", sa.Text(), nullable=False),
        sa.Column("normalized_hash", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_job_snapshots_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_job_snapshots_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_snapshots")),
        sa.UniqueConstraint(
            "application_id",
            "source_hash",
            name=op.f("uq_job_snapshots_application_id_source_hash"),
        ),
        sa.UniqueConstraint(
            "application_id", "id", name=op.f("uq_job_snapshots_application_id_id")
        ),
        sa.UniqueConstraint(
            "application_id",
            "version_number",
            name=op.f("uq_job_snapshots_application_id_version_number"),
        ),
    )
    op.create_table(
        "operations",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("sources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("reasoning_effort", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("safe_failure_detail", sa.Text(), nullable=True),
        sa.Column("failure_reason", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("withheld_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("technical_log_reference", sa.Text(), nullable=True),
        sa.Column("retry_of_operation_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("attempts_completed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status IN ('succeeded', 'failed', 'cancelled', 'interrupted')) = (finished_at IS NOT NULL)",
            name=op.f("ck_operations_terminal_finished_at"),
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR failure_code IN ('SOURCE_CHANGED', 'PROVIDER_TIMEOUT', 'PROVIDER_RATE_LIMITED', 'PROVIDER_UNAVAILABLE', 'PROVIDER_REFUSED', 'INVALID_OUTPUT', 'CLAIM_REVIEW_UNCERTAIN', 'CLAIM_REVIEW_UNSUPPORTED', 'SCHEMA_VIOLATION', 'RENDER_FAILED', 'BROWSER_START_FAILED', 'MISSING_FACT_RENDERING', 'VALIDATION_EXECUTION_FAILED', 'CANCELLED_BEFORE_ACTIVATION', 'PROVIDER_NOT_CONFIGURED')",
            name=op.f("ck_operations_failure_code"),
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR status IN ('failed', 'cancelled')",
            name=op.f("ck_operations_failure_status"),
        ),
        sa.CheckConstraint(
            "failure_reason IS NULL OR (jsonb_typeof(failure_reason) = 'object' AND failure_reason ? 'code')",
            name=op.f("ck_operations_failure_reason_shape"),
        ),
        sa.CheckConstraint(
            "failure_reason IS NULL OR status IN ('failed', 'cancelled')",
            name=op.f("ck_operations_failure_reason_status"),
        ),
        sa.CheckConstraint(
            "withheld_claims IS NULL OR status = 'succeeded'",
            name=op.f("ck_operations_withheld_claims_status"),
        ),
        sa.CheckConstraint(
            "withheld_claims IS NULL OR (jsonb_typeof(withheld_claims) = 'object' AND withheld_claims ? 'code')",
            name=op.f("ck_operations_withheld_claims_shape"),
        ),
        sa.CheckConstraint(
            "operation_type IN ('analyze_job', 'create_draft', 'regenerate_section', 'regenerate_claim', 'render_document')",
            name=op.f("ck_operations_operation_type"),
        ),
        sa.CheckConstraint(
            "reasoning_effort IS NULL OR reasoning_effort IN ('low', 'medium', 'high')",
            name=op.f("ck_operations_reasoning_effort"),
        ),
        sa.CheckConstraint(
            "safe_failure_detail IS NULL OR status IN ('failed', 'cancelled')",
            name=op.f("ck_operations_failure_detail_status"),
        ),
        sa.CheckConstraint(
            "status != 'failed' OR failure_code IS NOT NULL", name=op.f("ck_operations_failed_code")
        ),
        sa.CheckConstraint(
            "status != 'running' OR lease_owner IS NOT NULL",
            name=op.f("ck_operations_running_lease"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted')",
            name=op.f("ck_operations_status"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('succeeded', 'failed', 'cancelled', 'interrupted') OR lease_owner IS NULL",
            name=op.f("ck_operations_terminal_lease"),
        ),
        sa.CheckConstraint(
            "attempts_completed >= 0", name=op.f("ck_operations_attempts_completed_nonnegative")
        ),
        sa.CheckConstraint(
            "length(payload_hash) = 64", name=op.f("ck_operations_payload_hash_length")
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) > 0", name=op.f("ck_operations_idempotency_key_nonempty")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_operations_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_operation_id"],
            ["operations.id"],
            name=op.f("fk_operations_retry_of_operation_id_operations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operations")),
        sa.UniqueConstraint(
            "operation_type",
            "idempotency_key",
            name=op.f("uq_operations_operation_type_idempotency_key"),
        ),
    )
    op.create_index(
        "idx_operations_application_status",
        "operations",
        ["application_id", "status", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "idx_operations_claimable",
        "operations",
        ["status", "next_attempt_at", "created_at", "id"],
        unique=False,
    )
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
            "event_type != 'status_correction' OR (corrects_event_id IS NOT NULL AND length(trim(reason)) > 0)",
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
            "from_status IS NULL OR from_status IN ('saved', 'applied', 'recruiter_screen', 'interview', 'assignment', 'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed')",
            name=op.f("ck_recruitment_events_from_status"),
        ),
        sa.CheckConstraint(
            "to_status IS NULL OR to_status IN ('saved', 'applied', 'recruiter_screen', 'interview', 'assignment', 'final_stage', 'offer', 'accepted', 'rejected', 'withdrawn', 'closed')",
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
        "job_analyses",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("job_snapshot_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("structured_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_job_analyses_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["application_id", "job_snapshot_id"],
            ["job_snapshots.application_id", "job_snapshots.id"],
            name=op.f("fk_job_analyses_application_id_job_snapshot_id_job_snapshots"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_job_analyses_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_analyses")),
        sa.UniqueConstraint("application_id", "id", name=op.f("uq_job_analyses_application_id_id")),
        sa.UniqueConstraint(
            "application_id",
            "version_number",
            name=op.f("uq_job_analyses_application_id_version_number"),
        ),
    )
    op.create_table(
        "operation_outputs",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("operation_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("output_type", sa.Text(), nullable=False),
        sa.Column("output_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "active = (activated_at IS NOT NULL)",
            name=op.f("ck_operation_outputs_active_activation"),
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name=op.f("fk_operation_outputs_operation_id_operations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operation_outputs")),
        sa.UniqueConstraint(
            "operation_id",
            "output_type",
            "output_id",
            name=op.f("uq_operation_outputs_operation_id_output_type_output_id"),
        ),
    )
    op.create_index(
        "idx_operation_outputs_operation",
        "operation_outputs",
        ["operation_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "operation_resource_leases",
        sa.Column("resource_kind", sa.Text(), nullable=False),
        sa.Column("resource_key", sa.Text(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "resource_kind IN ('application_mutation', 'render_browser', 'ai')",
            name=op.f("ck_operation_resource_leases_resource_kind"),
        ),
        sa.CheckConstraint("slot >= 0", name=op.f("ck_operation_resource_leases_slot_nonnegative")),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name=op.f("fk_operation_resource_leases_operation_id_operations"),
        ),
        sa.PrimaryKeyConstraint(
            "resource_kind", "resource_key", "slot", name=op.f("pk_operation_resource_leases")
        ),
        sa.UniqueConstraint(
            "operation_id",
            "resource_kind",
            "resource_key",
            name=op.f("uq_operation_resource_leases_operation_id_resource_kind_resource_key"),
        ),
    )
    op.create_index(
        "idx_operation_resource_leases_operation",
        "operation_resource_leases",
        ["operation_id"],
        unique=False,
    )
    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("artifact_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("track", sa.Text(), nullable=True),
        sa.Column("profile", sa.Text(), nullable=True),
        sa.Column("emphasis", sa.Text(), nullable=True),
        sa.Column("facts_version", sa.Text(), nullable=True),
        sa.Column("job_snapshot_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "lifecycle_status = 'provider-output'",
            name=op.f("ck_artifact_versions_lifecycle_status"),
        ),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_artifact_versions_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_artifact_versions_artifact_id_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["job_snapshot_id"],
            ["job_snapshots.id"],
            name=op.f("fk_artifact_versions_job_snapshot_id_job_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_versions")),
        sa.UniqueConstraint(
            "artifact_id",
            "version_number",
            name=op.f("uq_artifact_versions_artifact_id_version_number"),
        ),
        sa.UniqueConstraint("path", name=op.f("uq_artifact_versions_path")),
    )
    op.create_index("idx_versions_artifact", "artifact_versions", ["artifact_id"], unique=False)
    # Mutable by design (state-and-use-cases.md §2), so it is a mutable table exception.
    op.create_table(
        "cv_documents",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("analysis_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("profile_version", sa.Text(), nullable=False),
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
        sa.Column("job_snapshot_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("document_hash", sa.Text(), nullable=True),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("html_sha256", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("pdf_sha256", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(submission_type = 'internal' AND "
            + " AND ".join(f"{name} IS NOT NULL" for name in INTERNAL_REFERENCES)
            + ") OR (submission_type = 'external' AND "
            + " AND ".join(f"{name} IS NULL" for name in INTERNAL_REFERENCES)
            + ")",
            name=op.f("ck_submissions_references"),
        ),
        sa.CheckConstraint(
            "(document_hash IS NULL OR length(document_hash) = 64) "
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
        sa.ForeignKeyConstraint(
            ["application_id", "job_snapshot_id"],
            ["job_snapshots.application_id", "job_snapshots.id"],
            name=op.f("fk_submissions_application_id_job_snapshot_id_job_snapshots"),
            ondelete="RESTRICT",
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
    op.execute(IMMUTABILITY_SQL)
    op.execute(TRANSITION_GUARDS_SQL)


def downgrade() -> None:
    op.drop_index("idx_submissions_application", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("cv_documents")
    op.drop_index("idx_versions_artifact", table_name="artifact_versions")
    op.drop_table("artifact_versions")
    op.drop_index("idx_operation_resource_leases_operation", table_name="operation_resource_leases")
    op.drop_table("operation_resource_leases")
    op.drop_index("idx_operation_outputs_operation", table_name="operation_outputs")
    op.drop_table("operation_outputs")
    op.drop_table("job_analyses")
    op.drop_index("idx_recruitment_events_application", table_name="recruitment_events")
    op.drop_table("recruitment_events")
    op.drop_index("idx_operations_claimable", table_name="operations")
    op.drop_index("idx_operations_application_status", table_name="operations")
    op.drop_table("operations")
    op.drop_table("job_snapshots")
    op.drop_index("idx_fact_events_fact", table_name="fact_events")
    op.drop_table("fact_events")
    op.drop_index("idx_audit_records_application", table_name="audit_records")
    op.drop_table("audit_records")
    op.drop_table("artifacts")
    op.drop_index("idx_knowledge_mutation_journal_state", table_name="knowledge_mutation_journal")
    op.drop_table("knowledge_mutation_journal")
    op.drop_table("applications")
    op.drop_table("app_settings")
    op.execute("DROP FUNCTION cv_guard_knowledge_mutation_transition()")
    op.execute("DROP FUNCTION cv_guard_operation_output_activation()")
    op.execute("DROP FUNCTION cv_guard_terminal_operation_update()")
    op.execute("DROP FUNCTION cv_reject_protected_delete()")
    op.execute("DROP FUNCTION cv_reject_immutable_change()")
    for table_name in reversed(
        ("audit_records", "fact_events", "recruitment_events", "submissions")
    ):
        op.execute(sa.schema.DropSequence(sa.Sequence(f"{table_name}_seq_seq")))
