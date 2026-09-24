"""structured Operation failure reason and PROVIDER_NOT_CONFIGURED

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24

Two additions to `operations`, both nullable and additive:

* `failure_reason` (JSONB): the failure's reason in a closed vocabulary with typed
  parameters, written when a failure is recorded. Existing rows keep NULL: a record
  never carried a structured reason, and none is derived for it after the fact.
* `PROVIDER_NOT_CONFIGURED` joins the failure codes. Rows already failed for want of a
  provider stay `PROVIDER_REFUSED`, the code they were recorded under.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASELINE_CODES = (
    "'SOURCE_CHANGED', 'PROVIDER_TIMEOUT', 'PROVIDER_RATE_LIMITED', 'PROVIDER_UNAVAILABLE', "
    "'PROVIDER_REFUSED', 'INVALID_OUTPUT', 'SCHEMA_VIOLATION', 'RENDER_FAILED', "
    "'BROWSER_START_FAILED', 'MISSING_FACT_RENDERING', 'VALIDATION_EXECUTION_FAILED', "
    "'CANCELLED_BEFORE_ACTIVATION', 'CLAIM_REVIEW_UNCERTAIN', 'CLAIM_REVIEW_UNSUPPORTED'"
)
_CODES = _BASELINE_CODES + ", 'PROVIDER_NOT_CONFIGURED'"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_operations_failure_code"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_failure_code"),
        "operations",
        f"failure_code IS NULL OR failure_code IN ({_CODES})",
    )
    op.add_column(
        "operations",
        sa.Column("failure_reason", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_operations_failure_reason_status"),
        "operations",
        "failure_reason IS NULL OR status IN ('failed', 'cancelled')",
    )
    op.create_check_constraint(
        op.f("ck_operations_failure_reason_shape"),
        "operations",
        "failure_reason IS NULL OR "
        "(jsonb_typeof(failure_reason) = 'object' AND failure_reason ? 'code')",
    )


def downgrade() -> None:
    # A row recorded under the new code cannot be expressed in the baseline schema, and
    # a failure already written is not rewritten to fit it: refuse instead.
    remaining = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM operations WHERE failure_code = 'PROVIDER_NOT_CONFIGURED'"
            )
        )
        .scalar_one()
    )
    if remaining:
        raise RuntimeError(
            f"{remaining} Operation(s) failed with PROVIDER_NOT_CONFIGURED; "
            "the baseline schema cannot hold them"
        )
    op.drop_constraint(op.f("ck_operations_failure_reason_shape"), "operations", type_="check")
    op.drop_constraint(op.f("ck_operations_failure_reason_status"), "operations", type_="check")
    op.drop_column("operations", "failure_reason")
    op.drop_constraint(op.f("ck_operations_failure_code"), "operations", type_="check")
    op.create_check_constraint(
        op.f("ck_operations_failure_code"),
        "operations",
        f"failure_code IS NULL OR failure_code IN ({_BASELINE_CODES})",
    )
