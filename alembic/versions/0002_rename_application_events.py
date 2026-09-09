"""rename the draft-only application event log

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep the three existing append-only records intact. Revision 0001 originally
    # created this table as application_events; editing that applied migration to
    # rename it made existing databases claim to be current while lacking the table
    # used by approval and archival. Some development/test databases were instead
    # created after that edit and already have the new name while still reporting
    # revision 0001, so upgrading those is deliberately a no-op.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('application_events') IS NOT NULL THEN
                ALTER TABLE application_events RENAME TO draft_lifecycle_events;
                ALTER TABLE draft_lifecycle_events
                    RENAME CONSTRAINT pk_application_events TO pk_draft_lifecycle_events;
                ALTER TABLE draft_lifecycle_events
                    RENAME CONSTRAINT fk_application_events_application_id_applications
                    TO fk_draft_lifecycle_events_application_id_applications;
                ALTER TRIGGER no_update_application_events ON draft_lifecycle_events
                    RENAME TO no_update_draft_lifecycle_events;
                ALTER TRIGGER no_delete_application_events ON draft_lifecycle_events
                    RENAME TO no_delete_draft_lifecycle_events;
            ELSIF to_regclass('draft_lifecycle_events') IS NULL THEN
                RAISE EXCEPTION
                    'neither application_events nor draft_lifecycle_events exists';
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TRIGGER no_delete_draft_lifecycle_events ON draft_lifecycle_events "
        "RENAME TO no_delete_application_events"
    )
    op.execute(
        "ALTER TRIGGER no_update_draft_lifecycle_events ON draft_lifecycle_events "
        "RENAME TO no_update_application_events"
    )
    op.execute(
        "ALTER TABLE draft_lifecycle_events "
        "RENAME CONSTRAINT fk_draft_lifecycle_events_application_id_applications "
        "TO fk_application_events_application_id_applications"
    )
    op.execute(
        "ALTER TABLE draft_lifecycle_events "
        "RENAME CONSTRAINT pk_draft_lifecycle_events TO pk_application_events"
    )
    op.rename_table("draft_lifecycle_events", "application_events")
