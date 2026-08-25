"""postgresql baseline

Revision ID: 0001
Revises:
Create Date: 2026-08-25 13:32:47.013742
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMMUTABILITY_FUNCTIONS_SQL = """
CREATE FUNCTION cv_reject_immutable_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable record';
END;
$$;

CREATE FUNCTION cv_reject_protected_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable record';
END;
$$;
"""

IMMUTABILITY_TRIGGERS_SQL = """
DO $$
DECLARE
    table_name text;
    missing_exceptions text[];
    mutable_exceptions constant text[] := ARRAY[
        'applications',
        'working_drafts',
        'operations',
        'operation_resource_leases',
        'operation_outputs',
        'idempotency_receipts',
        'knowledge_mutation_journal',
        'workspace_settings'
    ];
BEGIN
    SELECT array_agg(exception_name ORDER BY exception_name)
    INTO missing_exceptions
    FROM unnest(mutable_exceptions) AS exception_name
    WHERE NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_tables
        WHERE schemaname = current_schema()
          AND tablename = exception_name
    );

    IF missing_exceptions IS NOT NULL THEN
        RAISE EXCEPTION 'mutable table exceptions do not exist: %', missing_exceptions;
    END IF;

    FOR table_name IN
        SELECT tablename
        FROM pg_catalog.pg_tables
        WHERE schemaname = current_schema()
          AND tablename != 'alembic_version'
          AND tablename != ALL(mutable_exceptions)
        ORDER BY tablename
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change()',
            'no_update_' || table_name,
            table_name
        );
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change()',
            'no_delete_' || table_name,
            table_name
        );
    END LOOP;

    FOREACH table_name IN ARRAY ARRAY[
        'operations',
        'operation_outputs',
        'idempotency_receipts',
        'knowledge_mutation_journal'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION cv_reject_protected_delete()',
            'prevent_delete_' || table_name,
            table_name
        );
    END LOOP;
END;
$$;
"""

TRANSITION_GUARDS_SQL = """
CREATE FUNCTION cv_guard_terminal_operation_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT (OLD.status NOT IN ('succeeded', 'failed', 'cancelled', 'interrupted')) THEN
        RAISE EXCEPTION 'immutable terminal operation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER prevent_update_terminal_operations
BEFORE UPDATE ON operations
FOR EACH ROW EXECUTE FUNCTION cv_guard_terminal_operation_update();

CREATE FUNCTION cv_guard_operation_output_activation() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    operation_status text;
    operation_cancellation_requested_at text;
BEGIN
    SELECT status, cancellation_requested_at
    INTO operation_status, operation_cancellation_requested_at
    FROM operations
    WHERE id = OLD.operation_id;

    IF NOT (
        OLD.active = FALSE
        AND NEW.active = TRUE
        AND NEW.activated_at IS NOT NULL
        AND OLD.id = NEW.id
        AND OLD.operation_id = NEW.operation_id
        AND OLD.output_type = NEW.output_type
        AND OLD.output_id = NEW.output_id
        AND OLD.created_at = NEW.created_at
        AND operation_status = 'running'
        AND operation_cancellation_requested_at IS NULL
    ) THEN
        RAISE EXCEPTION 'invalid operation output update';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER valid_operation_output_activation
BEFORE UPDATE ON operation_outputs
FOR EACH ROW EXECUTE FUNCTION cv_guard_operation_output_activation();

CREATE FUNCTION cv_guard_idempotency_receipt_completion() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT (
        OLD.status = 'pending'
        AND NEW.status = 'completed'
        AND OLD.id = NEW.id
        AND OLD.installation_id = NEW.installation_id
        AND OLD.command_type = NEW.command_type
        AND OLD.idempotency_key = NEW.idempotency_key
        AND OLD.payload_json = NEW.payload_json
        AND OLD.payload_hash = NEW.payload_hash
        AND OLD.reserved_entity_id = NEW.reserved_entity_id
        AND OLD.created_at = NEW.created_at
        AND NEW.result_json IS NOT NULL
        AND NEW.completed_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'invalid idempotency receipt update';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER valid_idempotency_receipt_completion
BEFORE UPDATE ON idempotency_receipts
FOR EACH ROW EXECUTE FUNCTION cv_guard_idempotency_receipt_completion();

CREATE FUNCTION cv_guard_knowledge_mutation_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT (
        OLD.state = 'PREPARED'
        AND NEW.state IN ('COMMITTED', 'QUARANTINED')
        AND OLD.id = NEW.id
        AND OLD.mutation_type = NEW.mutation_type
        AND OLD.source_reference = NEW.source_reference
        AND OLD.staged_reference = NEW.staged_reference
        AND OLD.old_sha256 = NEW.old_sha256
        AND OLD.new_sha256 = NEW.new_sha256
        AND OLD.db_mutation_type = NEW.db_mutation_type
        AND OLD.db_mutation_id = NEW.db_mutation_id
        AND OLD.db_mutation_json = NEW.db_mutation_json
        AND OLD.recovery_strategy = NEW.recovery_strategy
        AND OLD.prepared_at = NEW.prepared_at
    ) THEN
        RAISE EXCEPTION 'invalid knowledge mutation transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER valid_knowledge_mutation_transition
BEFORE UPDATE ON knowledge_mutation_journal
FOR EACH ROW EXECUTE FUNCTION cv_guard_knowledge_mutation_transition();
"""


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "applications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("target_role", sa.Text(), nullable=False),
        sa.Column("normalized_role", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("track", sa.Text(), nullable=True),
        sa.Column("profile", sa.Text(), nullable=True),
        sa.Column("emphasis", sa.Text(), nullable=True),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("fit_level", sa.Text(), nullable=True),
        sa.Column("current_status", sa.Text(), nullable=False),
        sa.Column("last_contact_date", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("next_action_date", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("terminal_outcome", sa.Text(), nullable=True),
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
        "idempotency_receipts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("installation_id", sa.Text(), nullable=False),
        sa.Column("command_type", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("reserved_entity_id", sa.String(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name=op.f("ck_idempotency_receipts_completed_at"),
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (result_json IS NOT NULL)",
            name=op.f("ck_idempotency_receipts_result"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')", name=op.f("ck_idempotency_receipts_status")
        ),
        sa.CheckConstraint(
            "length(payload_hash) = 64", name=op.f("ck_idempotency_receipts_payload_hash_length")
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) > 0",
            name=op.f("ck_idempotency_receipts_idempotency_key_nonempty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_receipts")),
        sa.UniqueConstraint(
            "installation_id",
            "command_type",
            "idempotency_key",
            name=op.f("uq_idempotency_receipts_installation_id_command_type_idempotency_key"),
        ),
    )
    op.create_table(
        "knowledge_mutation_journal",
        sa.Column("id", sa.String(), nullable=False),
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
        sa.Column("prepared_at", sa.Text(), nullable=False),
        sa.Column("committed_at", sa.Text(), nullable=True),
        sa.Column("quarantined_at", sa.Text(), nullable=True),
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
        "workspace_settings",
        sa.Column("singleton_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("edit_version", sa.Integer(), nullable=False),
        sa.Column("auto_generate_when_review_not_required", sa.Boolean(), nullable=False),
        sa.Column("ai_enabled_override", sa.Boolean(), nullable=True),
        sa.Column("default_execution_mode", sa.Text(), nullable=False),
        sa.Column("open_browser_on_launch", sa.Boolean(), nullable=False),
        sa.Column("ui_density", sa.Text(), nullable=False),
        sa.Column("ui_text_size", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "default_execution_mode IN ('deterministic', 'ai')",
            name=op.f("ck_workspace_settings_default_execution_mode"),
        ),
        sa.CheckConstraint(
            "ui_density IN ('comfortable', 'compact')",
            name=op.f("ck_workspace_settings_ui_density"),
        ),
        sa.CheckConstraint(
            "ui_text_size IN ('normal', 'large')", name=op.f("ck_workspace_settings_ui_text_size")
        ),
        sa.CheckConstraint(
            "edit_version > 0", name=op.f("ck_workspace_settings_edit_version_positive")
        ),
        sa.CheckConstraint("singleton_id = 1", name=op.f("ck_workspace_settings_singleton")),
        sa.PrimaryKeyConstraint("singleton_id", name=op.f("pk_workspace_settings")),
    )
    op.create_table(
        "application_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_application_events_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_events")),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=True),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("logical_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
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
    op.create_index("idx_artifacts_application", "artifacts", ["application_id"], unique=False)
    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("client", sa.Text(), nullable=False),
        sa.Column("installation_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column(
            "details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')", name=op.f("ck_audit_records_actor_type")
        ),
        sa.CheckConstraint(
            "client IN ('web', 'cli', 'worker')", name=op.f("ck_audit_records_client")
        ),
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
        ["application_id", "occurred_at", "id"],
        unique=False,
    )
    op.create_table(
        "fact_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("fact_id", sa.String(), nullable=False),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=True),
        sa.Column("claim_id", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("fact_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fact_hash", sa.Text(), nullable=False),
        sa.Column("facts_version", sa.Text(), nullable=False),
        sa.Column("lifecycle_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_fact_events_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fact_events")),
    )
    op.create_index("idx_fact_events_fact", "fact_events", ["fact_id"], unique=False)
    op.create_table(
        "generation_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("rendering_rules_version", sa.Text(), nullable=False),
        sa.Column("facts_version", sa.Text(), nullable=False),
        sa.Column("ai_provider", sa.Text(), nullable=False),
        sa.Column("ai_model", sa.Text(), nullable=False),
        sa.Column("task_contract_version", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("job_analysis_version", sa.Text(), nullable=False),
        sa.Column(
            "instruction_overrides_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_generation_runs_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_runs")),
    )
    op.create_table(
        "job_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("payload_path", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.Column("normalized_hash", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.Text(), nullable=False),
        sa.Column("source_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("prior_snapshot_id", sa.String(), nullable=True),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_job_snapshots_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_job_snapshots_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["prior_snapshot_id"],
            ["job_snapshots.id"],
            name=op.f("fk_job_snapshots_prior_snapshot_id_job_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_snapshots")),
        sa.UniqueConstraint(
            "application_id",
            "content_hash",
            name=op.f("uq_job_snapshots_application_id_content_hash"),
        ),
        sa.UniqueConstraint(
            "application_id",
            "version_number",
            name=op.f("uq_job_snapshots_application_id_version_number"),
        ),
    )
    op.create_index("idx_snapshots_application", "job_snapshots", ["application_id"], unique=False)
    op.create_table(
        "operations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("installation_id", sa.Text(), nullable=False),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("sources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.Text(), nullable=True),
        sa.Column("heartbeat_at", sa.Text(), nullable=True),
        sa.Column("cancellation_requested_at", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("safe_failure_detail", sa.Text(), nullable=True),
        sa.Column("technical_log_reference", sa.Text(), nullable=True),
        sa.Column("retry_of_operation_id", sa.String(), nullable=True),
        sa.Column("attempts_completed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(status IN ('succeeded', 'failed', 'cancelled', 'interrupted')) = (finished_at IS NOT NULL)",
            name=op.f("ck_operations_terminal_finished_at"),
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR failure_code IN ('SOURCE_CHANGED', 'PROVIDER_TIMEOUT', 'PROVIDER_RATE_LIMITED', 'PROVIDER_UNAVAILABLE', 'PROVIDER_REFUSED', 'INVALID_OUTPUT', 'SCHEMA_VIOLATION', 'RENDER_FAILED', 'BROWSER_START_FAILED', 'VALIDATION_EXECUTION_FAILED', 'CANCELLED_BEFORE_ACTIVATION')",
            name=op.f("ck_operations_failure_code"),
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR status IN ('failed', 'cancelled')",
            name=op.f("ck_operations_failure_status"),
        ),
        sa.CheckConstraint(
            "operation_type IN ('analyze_job', 'propose_selection_plan', 'create_draft', 'regenerate_section', 'regenerate_claim', 'render_revision')",
            name=op.f("ck_operations_operation_type"),
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
            "(lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL)",
            name=op.f("ck_operations_lease_fields"),
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
            "installation_id",
            "operation_type",
            "idempotency_key",
            name=op.f("uq_operations_installation_id_operation_type_idempotency_key"),
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
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("corrects_event_id", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("client", sa.Text(), nullable=False),
        sa.Column("installation_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')", name=op.f("ck_recruitment_events_actor_type")
        ),
        sa.CheckConstraint(
            "client IN ('web', 'cli', 'worker')", name=op.f("ck_recruitment_events_client")
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
        ["application_id", "occurred_at", "id"],
        unique=False,
    )
    op.create_table(
        "job_analyses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("job_snapshot_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("structured_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_job_analyses_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_job_analyses_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["job_snapshot_id"],
            ["job_snapshots.id"],
            name=op.f("fk_job_analyses_job_snapshot_id_job_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_analyses")),
        sa.UniqueConstraint(
            "application_id",
            "version_number",
            name=op.f("uq_job_analyses_application_id_version_number"),
        ),
    )
    op.create_index("idx_analyses_application", "job_analyses", ["application_id"], unique=False)
    op.create_table(
        "operation_outputs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("operation_id", sa.String(), nullable=False),
        sa.Column("output_type", sa.Text(), nullable=False),
        sa.Column("output_id", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.Text(), nullable=True),
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
        sa.Column("operation_id", sa.String(), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=False),
        sa.Column("lease_expires_at", sa.Text(), nullable=False),
        sa.Column("heartbeat_at", sa.Text(), nullable=False),
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
        "selection_plans",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("job_analysis_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidate_context_version", sa.Text(), nullable=False),
        sa.Column("candidate_context_hash", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("selection_policy_version", sa.Text(), nullable=False),
        sa.Column(
            "track_emphasis_dependencies_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_selection_plans_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_selection_plans_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["job_analysis_id"],
            ["job_analyses.id"],
            name=op.f("fk_selection_plans_job_analysis_id_job_analyses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_selection_plans")),
        sa.UniqueConstraint(
            "application_id",
            "version_number",
            name=op.f("uq_selection_plans_application_id_version_number"),
        ),
    )
    op.create_table(
        "working_drafts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("job_analysis_id", sa.String(), nullable=False),
        sa.Column("selection_plan_id", sa.String(), nullable=False),
        sa.Column("parent_revision_id", sa.String(), nullable=True),
        sa.Column("source_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edit_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "edit_version > 0", name=op.f("ck_working_drafts_edit_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_working_drafts_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["job_analysis_id"],
            ["job_analyses.id"],
            name=op.f("fk_working_drafts_job_analysis_id_job_analyses"),
        ),
        sa.ForeignKeyConstraint(
            ["selection_plan_id"],
            ["selection_plans.id"],
            name=op.f("fk_working_drafts_selection_plan_id_selection_plans"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_working_drafts")),
    )
    op.create_index(
        "one_active_working_draft_per_application",
        "working_drafts",
        ["application_id"],
        unique=True,
        postgresql_where=sa.text("active IS true"),
    )
    op.create_table(
        "approved_revisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("job_snapshot_id", sa.String(), nullable=False),
        sa.Column("job_analysis_id", sa.String(), nullable=False),
        sa.Column("selection_plan_id", sa.String(), nullable=False),
        sa.Column("working_draft_id", sa.String(), nullable=False),
        sa.Column("draft_edit_version", sa.Integer(), nullable=False),
        sa.Column("draft_content_hash", sa.Text(), nullable=False),
        sa.Column("resume_json_path", sa.Text(), nullable=False),
        sa.Column("resume_json_hash", sa.Text(), nullable=False),
        sa.Column("resume_markdown_path", sa.Text(), nullable=False),
        sa.Column("resume_markdown_hash", sa.Text(), nullable=False),
        sa.Column("candidate_context_version", sa.Text(), nullable=False),
        sa.Column("candidate_context_hash", sa.Text(), nullable=False),
        sa.Column("facts_version", sa.Text(), nullable=False),
        sa.Column("knowledge_context_hash", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("selection_policy_version", sa.Text(), nullable=False),
        sa.Column(
            "track_emphasis_dependencies_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("validation_run_id", sa.String(), nullable=False),
        sa.Column(
            "validator_versions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "decision_provenance_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("approved_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "draft_edit_version > 0", name=op.f("ck_approved_revisions_draft_edit_version_positive")
        ),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_approved_revisions_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_approved_revisions_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["job_analysis_id"],
            ["job_analyses.id"],
            name=op.f("fk_approved_revisions_job_analysis_id_job_analyses"),
        ),
        sa.ForeignKeyConstraint(
            ["job_snapshot_id"],
            ["job_snapshots.id"],
            name=op.f("fk_approved_revisions_job_snapshot_id_job_snapshots"),
        ),
        sa.ForeignKeyConstraint(
            ["selection_plan_id"],
            ["selection_plans.id"],
            name=op.f("fk_approved_revisions_selection_plan_id_selection_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["validation_runs.id"],
            name="fk_approved_revisions_validation_run_id_validation_runs",
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(
            ["working_draft_id"],
            ["working_drafts.id"],
            name=op.f("fk_approved_revisions_working_draft_id_working_drafts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approved_revisions")),
        sa.UniqueConstraint(
            "application_id",
            "version_number",
            name=op.f("uq_approved_revisions_application_id_version_number"),
        ),
        sa.UniqueConstraint(
            "resume_json_path", name=op.f("uq_approved_revisions_resume_json_path")
        ),
        sa.UniqueConstraint(
            "resume_markdown_path", name=op.f("uq_approved_revisions_resume_markdown_path")
        ),
        sa.UniqueConstraint(
            "validation_run_id", name=op.f("uq_approved_revisions_validation_run_id")
        ),
    )
    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.Text(), nullable=True),
        sa.Column("track", sa.Text(), nullable=True),
        sa.Column("profile", sa.Text(), nullable=True),
        sa.Column("emphasis", sa.Text(), nullable=True),
        sa.Column("facts_version", sa.Text(), nullable=True),
        sa.Column("job_snapshot_id", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("revision_id", sa.String(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["approved_revisions.id"],
            name=op.f("fk_artifact_versions_revision_id_approved_revisions"),
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
    op.create_index("idx_versions_revision", "artifact_versions", ["revision_id"], unique=False)
    op.create_table(
        "decision_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("artifact_version_id", sa.String(), nullable=True),
        sa.Column("job_snapshot_id", sa.String(), nullable=False),
        sa.Column("job_analysis_id", sa.String(), nullable=False),
        sa.Column("structured_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_decision_records_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"],
            ["artifact_versions.id"],
            name=op.f("fk_decision_records_artifact_version_id_artifact_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["job_analysis_id"],
            ["job_analyses.id"],
            name=op.f("fk_decision_records_job_analysis_id_job_analyses"),
        ),
        sa.ForeignKeyConstraint(
            ["job_snapshot_id"],
            ["job_snapshots.id"],
            name=op.f("fk_decision_records_job_snapshot_id_job_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_records")),
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("submission_type", sa.Text(), nullable=False),
        sa.Column("approved_revision_id", sa.String(), nullable=True),
        sa.Column("artifact_version_id", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.Text(), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(submission_type = 'internal' AND approved_revision_id IS NOT NULL AND artifact_version_id IS NOT NULL) OR (submission_type = 'external' AND approved_revision_id IS NULL)",
            name=op.f("ck_submissions_references"),
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
            ["approved_revision_id"],
            ["approved_revisions.id"],
            name=op.f("fk_submissions_approved_revision_id_approved_revisions"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"],
            ["artifact_versions.id"],
            name=op.f("fk_submissions_artifact_version_id_artifact_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
        sa.UniqueConstraint("artifact_version_id", name=op.f("uq_submissions_artifact_version_id")),
    )
    op.create_index(
        "idx_submissions_application",
        "submissions",
        ["application_id", "submitted_at", "id"],
        unique=False,
    )
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("application_id", sa.String(), nullable=False),
        sa.Column("artifact_version_id", sa.String(), nullable=True),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("working_draft_id", sa.String(), nullable=True),
        sa.Column("edit_version", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("job_snapshot_id", sa.String(), nullable=True),
        sa.Column("job_analysis_id", sa.String(), nullable=True),
        sa.Column("selection_plan_id", sa.String(), nullable=True),
        sa.Column("knowledge_context_hash", sa.Text(), nullable=True),
        sa.Column(
            "validator_versions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_validation_runs_application_id_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"],
            ["artifact_versions.id"],
            name=op.f("fk_validation_runs_artifact_version_id_artifact_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["job_analysis_id"],
            ["job_analyses.id"],
            name=op.f("fk_validation_runs_job_analysis_id_job_analyses"),
        ),
        sa.ForeignKeyConstraint(
            ["job_snapshot_id"],
            ["job_snapshots.id"],
            name=op.f("fk_validation_runs_job_snapshot_id_job_snapshots"),
        ),
        sa.ForeignKeyConstraint(
            ["selection_plan_id"],
            ["selection_plans.id"],
            name=op.f("fk_validation_runs_selection_plan_id_selection_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["working_draft_id"],
            ["working_drafts.id"],
            name=op.f("fk_validation_runs_working_draft_id_working_drafts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_runs")),
    )
    op.create_foreign_key(
        "fk_approved_revisions_validation_run_id_validation_runs",
        "approved_revisions",
        "validation_runs",
        ["validation_run_id"],
        ["id"],
    )
    op.execute(IMMUTABILITY_FUNCTIONS_SQL)
    op.execute(IMMUTABILITY_TRIGGERS_SQL)
    op.execute(TRANSITION_GUARDS_SQL)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "fk_approved_revisions_validation_run_id_validation_runs",
        "approved_revisions",
        type_="foreignkey",
    )
    op.drop_table("validation_runs")
    op.drop_index("idx_submissions_application", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("decision_records")
    op.drop_index("idx_versions_revision", table_name="artifact_versions")
    op.drop_index("idx_versions_artifact", table_name="artifact_versions")
    op.drop_table("artifact_versions")
    op.drop_table("approved_revisions")
    op.drop_index(
        "one_active_working_draft_per_application",
        table_name="working_drafts",
        postgresql_where=sa.text("active IS true"),
    )
    op.drop_table("working_drafts")
    op.drop_table("selection_plans")
    op.drop_index("idx_operation_resource_leases_operation", table_name="operation_resource_leases")
    op.drop_table("operation_resource_leases")
    op.drop_index("idx_operation_outputs_operation", table_name="operation_outputs")
    op.drop_table("operation_outputs")
    op.drop_index("idx_analyses_application", table_name="job_analyses")
    op.drop_table("job_analyses")
    op.drop_index("idx_recruitment_events_application", table_name="recruitment_events")
    op.drop_table("recruitment_events")
    op.drop_index("idx_operations_claimable", table_name="operations")
    op.drop_index("idx_operations_application_status", table_name="operations")
    op.drop_table("operations")
    op.drop_index("idx_snapshots_application", table_name="job_snapshots")
    op.drop_table("job_snapshots")
    op.drop_table("generation_runs")
    op.drop_index("idx_fact_events_fact", table_name="fact_events")
    op.drop_table("fact_events")
    op.drop_index("idx_audit_records_application", table_name="audit_records")
    op.drop_table("audit_records")
    op.drop_index("idx_artifacts_application", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_table("application_events")
    op.drop_table("workspace_settings")
    op.drop_index("idx_knowledge_mutation_journal_state", table_name="knowledge_mutation_journal")
    op.drop_table("knowledge_mutation_journal")
    op.drop_table("idempotency_receipts")
    op.drop_table("applications")
    op.execute("DROP FUNCTION cv_guard_knowledge_mutation_transition()")
    op.execute("DROP FUNCTION cv_guard_idempotency_receipt_completion()")
    op.execute("DROP FUNCTION cv_guard_operation_output_activation()")
    op.execute("DROP FUNCTION cv_guard_terminal_operation_update()")
    op.execute("DROP FUNCTION cv_reject_protected_delete()")
    op.execute("DROP FUNCTION cv_reject_immutable_change()")
    # ### end Alembic commands ###
