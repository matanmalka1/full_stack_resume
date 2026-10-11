"""enable multiple users and add shared sign-in throttling

Isolation is complete before this revision removes ``users_single_user``. The
rate-limit table stores only hashed bucket keys, and PostgreSQL makes counters
shared by every API process (architecture §18.5).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-11 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM fact_events WHERE user_id IS NULL) THEN
            RAISE EXCEPTION
              'fact events must be assigned by import-knowledge before enabling multiple users';
          END IF;
        END; $$;
        """
    )
    op.execute(
        """
        DROP TRIGGER prevent_delete_fact_events ON fact_events;
        DROP TRIGGER guard_fact_event_owner ON fact_events;
        DROP FUNCTION cv_guard_fact_event_owner();
        """
    )
    op.alter_column("fact_events", "user_id", nullable=False)
    op.execute(
        """
        CREATE TRIGGER no_update_fact_events BEFORE UPDATE ON fact_events
          FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change();
        CREATE TRIGGER no_delete_fact_events BEFORE DELETE ON fact_events
          FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change();
        """
    )

    op.create_table(
        "rate_limit_buckets",
        sa.Column("bucket_type", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "bucket_type IN ('email_failure', 'client_attempt')",
            name=op.f("ck_rate_limit_buckets_bucket_type"),
        ),
        sa.CheckConstraint(
            "length(key_hash) = 64", name=op.f("ck_rate_limit_buckets_key_hash_length")
        ),
        sa.CheckConstraint("count > 0", name=op.f("ck_rate_limit_buckets_count_positive")),
        sa.PrimaryKeyConstraint(
            "bucket_type",
            "key_hash",
            "window_started_at",
            name=op.f("pk_rate_limit_buckets"),
        ),
    )
    op.create_index("ix_rate_limit_buckets_window", "rate_limit_buckets", ["window_started_at"])

    op.drop_index("ix_applications_user_id", table_name="applications")
    op.create_index("idx_applications_user_created", "applications", ["user_id", "created_at"])
    op.create_index("idx_applications_user_status", "applications", ["user_id", "current_status"])
    op.create_index("idx_applications_user_updated", "applications", ["user_id", "updated_at"])

    op.drop_index("users_single_user", table_name="users")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF (SELECT count(*) FROM users) > 1 THEN
            RAISE EXCEPTION 'cannot restore the single-user guard while multiple users exist';
          END IF;
        END; $$;
        """
    )
    op.create_index("users_single_user", "users", [sa.text("(true)")], unique=True)

    op.execute(
        """
        DROP TRIGGER no_update_fact_events ON fact_events;
        DROP TRIGGER no_delete_fact_events ON fact_events;
        """
    )
    op.alter_column("fact_events", "user_id", nullable=True)
    op.execute(
        """
        CREATE FUNCTION cv_guard_fact_event_owner() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.user_id IS NULL AND NEW.user_id IS NOT NULL
             AND (to_jsonb(NEW) - 'user_id') = (to_jsonb(OLD) - 'user_id') THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'immutable record';
        END; $$;
        CREATE TRIGGER guard_fact_event_owner BEFORE UPDATE ON fact_events
          FOR EACH ROW EXECUTE FUNCTION cv_guard_fact_event_owner();
        CREATE TRIGGER prevent_delete_fact_events BEFORE DELETE ON fact_events
          FOR EACH ROW EXECUTE FUNCTION cv_reject_protected_delete();
        """
    )

    op.drop_index("idx_applications_user_updated", table_name="applications")
    op.drop_index("idx_applications_user_status", table_name="applications")
    op.drop_index("idx_applications_user_created", table_name="applications")
    op.create_index("ix_applications_user_id", "applications", ["user_id"])

    op.drop_index("ix_rate_limit_buckets_window", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
