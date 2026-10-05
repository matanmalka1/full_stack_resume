"""operation failure codes: PRECONDITION_FAILED and INFRASTRUCTURE_FAILED

A refusal by the workflow and a storage failure each get their own code instead of
VALIDATION_EXECUTION_FAILED, which now means only that the engine itself failed.

A revision rather than an edit to 0001: a database already at 0001 keeps the CHECK
it was created with, and would reject the new codes when a failed Operation is
written. Rows already written keep their codes; nothing is rewritten.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = (
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
_AFTER = (*_BEFORE, "PRECONDITION_FAILED", "INFRASTRUCTURE_FAILED")


def _replace_check(codes: tuple[str, ...]) -> None:
    values = ", ".join(f"'{code}'" for code in codes)
    op.drop_constraint(op.f("ck_operations_failure_code"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_failure_code"),
        "operations",
        f"failure_code IS NULL OR failure_code IN ({values})",
    )


def upgrade() -> None:
    _replace_check(_AFTER)


def downgrade() -> None:
    # Refused by PostgreSQL while a row carries one of the new codes: a downgrade
    # never rewrites a recorded failure to make it fit.
    _replace_check(_BEFORE)
