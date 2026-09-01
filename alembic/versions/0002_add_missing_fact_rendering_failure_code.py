"""add the missing fact rendering Operation failure code

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CODES = (
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
NEW_CODES = (*OLD_CODES[:-2], "MISSING_FACT_RENDERING", *OLD_CODES[-2:])


def _predicate(codes: tuple[str, ...]) -> str:
    allowed = ", ".join(f"'{code}'" for code in codes)
    return f"failure_code IS NULL OR failure_code IN ({allowed})"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_operations_failure_code"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_failure_code"),
        "operations",
        _predicate(NEW_CODES),
    )


def downgrade() -> None:
    # Deliberately do not rewrite completed Operation evidence. PostgreSQL will
    # refuse this downgrade if a row already carries the new code.
    op.drop_constraint(op.f("ck_operations_failure_code"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_failure_code"),
        "operations",
        _predicate(OLD_CODES),
    )
