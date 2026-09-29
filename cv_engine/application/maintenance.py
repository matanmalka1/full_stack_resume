"""Maintenance operations: integrity reconciliation and data export.

These are not product capabilities - nothing here creates, edits, or approves a
record - so they live in the application layer, where any caller reaches them
without holding logic of its own.

This layer projects an export; it does not write one. Touching the filesystem
here would put storage layout in the layer that must stay independent of it,
so the CSV writer lives in `infrastructure/exports.py`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..util import utc_now
from .commands import BoundaryDTO
from .queries import ApplicationListView

EXPORT_SCHEMA_VERSION = "2.0"


EXPORT_FIELDS = [
    "id",
    "company",
    "target_role",
    "normalized_role",
    "language",
    "track",
    "profile",
    "emphasis",
    "current_status",
    "next_action",
    "next_action_date",
    "notes",
    "created_at",
    "updated_at",
]


class ApplicationExport(BoundaryDTO):
    """The full content of one export, with nothing written yet.

    The application layer decides what an export contains - which columns, in
    which order, under which schema version - and the caller decides where the
    bytes go. Writing files here would put storage layout in a layer that is
    not allowed to know any, and the CSV serialization itself is a presentation
    concern of the one client that asks for a CSV.
    """

    export_schema_version: str
    columns: list[str]
    rows: list[dict[str, Any]]
    generated_at: str

    @property
    def metadata(self) -> dict[str, Any]:
        """The sidecar record describing this export's schema."""
        return {
            "export_schema_version": self.export_schema_version,
            "columns": self.columns,
            "row_count": len(self.rows),
            "generated_at": self.generated_at,
        }


def build_application_export(applications: ApplicationListView) -> ApplicationExport:
    """Project applications onto the versioned export schema.

    The v1 export had no version marker, so a consumer could not tell which
    columns to expect. No such consumer was found in this repository, so the
    v2 export keeps the same columns and records the schema beside them rather
    than inventing a compatibility mode nothing asked for.
    """
    source = [item.model_dump(mode="json") for item in applications.items]
    return ApplicationExport(
        export_schema_version=EXPORT_SCHEMA_VERSION,
        columns=list(EXPORT_FIELDS),
        rows=[{field: row.get(field) for field in EXPORT_FIELDS} for row in source],
        generated_at=utc_now(),
    )


#: How long an unregistered payload must have been stored before it counts as
#: an orphan (architecture.md §7.1). Every writer registers its payload within
#: seconds of storing it - intake, provider evidence, and submission each store
#: and register in one command - so a payload still unregistered an hour later
#: was abandoned, and a younger one may still be on its way to registration.
ORPHAN_MIN_AGE = timedelta(hours=1)


class OrphanInventory(BoundaryDTO):
    """Unregistered payloads older than `ORPHAN_MIN_AGE`."""

    candidates: list[str]


class ReclaimResult(BoundaryDTO):
    """What one `reclaim_orphans()` call removed (architecture.md §7.1)."""

    removed: list[str]
