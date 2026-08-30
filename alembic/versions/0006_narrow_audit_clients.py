"""narrow audit clients to active process identities

The Web API is the only user-facing adapter and the worker is the only internal
execution host. No runtime writes `client='cli'`, so the database contract now
matches the application boundary instead of retaining a client that does not
exist. The upgrade does not rewrite immutable rows: if a database contains the
removed value, PostgreSQL refuses the new constraint and the migration fails.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = ("audit_records", "recruitment_events")


# `op.f` marks a name as already-final. Without it the metadata naming
# convention prefixes `ck_<table>_` a second time, and the migration fails
# looking for `ck_audit_records_ck_audit_records_client`.
def _replace_client_check(table_name: str, expression: str) -> None:
    op.drop_constraint(op.f(f"ck_{table_name}_client"), table_name, type_="check")
    op.create_check_constraint("client", table_name, expression)


def upgrade() -> None:
    # Adding a normal (validated) CHECK is deliberate. Existing `cli` rows are
    # not silently grandfathered into a schema that says they cannot exist.
    for table_name in TABLES:
        _replace_client_check(table_name, "client IN ('web', 'worker')")


def downgrade() -> None:
    for table_name in TABLES:
        _replace_client_check(table_name, "client IN ('web', 'cli', 'worker')")
