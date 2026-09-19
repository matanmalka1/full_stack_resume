"""add semantic claim-review failure codes

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE_CODES = (
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
_REVIEW_CODES = ("CLAIM_REVIEW_UNCERTAIN", "CLAIM_REVIEW_UNSUPPORTED")


def _failure_code_check(codes: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{code}'" for code in codes)
    return f"failure_code IS NULL OR failure_code IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_operations_failure_code"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_failure_code"),
        "operations",
        _failure_code_check(_BASE_CODES + _REVIEW_CODES),
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_operations_failure_code"), "operations", type_="check")
    op.execute(
        "UPDATE operations SET failure_code = 'INVALID_OUTPUT' "
        "WHERE failure_code IN ('CLAIM_REVIEW_UNCERTAIN', 'CLAIM_REVIEW_UNSUPPORTED')"
    )
    op.create_check_constraint(
        op.f("ck_operations_failure_code"),
        "operations",
        _failure_code_check(_BASE_CODES),
    )
