"""fact_events.user_id: a fact event gets its owner once

`fact_events` stays immutable except for one permitted transition: `user_id` from NULL
to a user, with no other column changing (docs/decisions/multi-user-accounts.md §4).
`import-knowledge` makes it for the rows written before Knowledge had an owner. The
shared `no_update`/`no_delete` pair is replaced by a guard that allows exactly that
transition and a delete-only refusal, the pattern terminal Operation rows already use.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER_GUARD_SQL = """
DROP TRIGGER no_update_fact_events ON fact_events;
DROP TRIGGER no_delete_fact_events ON fact_events;
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

RESTORE_IMMUTABILITY_SQL = """
DROP TRIGGER prevent_delete_fact_events ON fact_events;
DROP TRIGGER guard_fact_event_owner ON fact_events;
DROP FUNCTION cv_guard_fact_event_owner();
CREATE TRIGGER no_update_fact_events BEFORE UPDATE ON fact_events
  FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change();
CREATE TRIGGER no_delete_fact_events BEFORE DELETE ON fact_events
  FOR EACH ROW EXECUTE FUNCTION cv_reject_immutable_change();
"""


def upgrade() -> None:
    op.add_column(
        "fact_events",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_fact_events_user_id_users"), "fact_events", "users", ["user_id"], ["id"]
    )
    op.execute(OWNER_GUARD_SQL)


def downgrade() -> None:
    op.execute(RESTORE_IMMUTABILITY_SQL)
    op.drop_constraint(op.f("fk_fact_events_user_id_users"), "fact_events", type_="foreignkey")
    op.drop_column("fact_events", "user_id")
