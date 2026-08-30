"""drop open_browser_on_launch

Nothing consumes the setting: the API and the worker are started by whoever
runs them, and neither opens a browser. A stored preference no code reads is a
promise the product does not keep, so the column goes rather than staying as
dead configuration a future reader would try to honour.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("app_settings", "open_browser_on_launch")


def downgrade() -> None:
    # The prior default, so an older revision reads the value it expects.
    op.add_column(
        "app_settings",
        sa.Column(
            "open_browser_on_launch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("app_settings", "open_browser_on_launch", server_default=None)
