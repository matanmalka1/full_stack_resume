"""Maintenance operations: integrity reconciliation and data export.

These are not product capabilities - nothing here creates, edits, or approves a
record - so they live in the application layer, where any caller reaches them
without holding logic of its own.

This layer projects an export; it does not write one. Touching the filesystem
here would put storage layout in the layer that must stay independent of it,
so the CSV writer lives in `infrastructure/exports.py`.
"""

from __future__ import annotations

from typing import Any

from ..util import utc_now
from .commands import BoundaryDTO
from .queries import ApplicationListView

EXPORT_SCHEMA_VERSION = "3.0"


EXPORT_FIELDS = [
    "id",
    "company",
    "target_role",
    "normalized_role",
    "language",
    "track",
    "profile",
    "emphasis",
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

    The schema version is recorded beside the columns so a consumer can tell which
    to expect. v3 dropped the recruitment-tracking columns.
    """
    source = [item.model_dump(mode="json") for item in applications.items]
    return ApplicationExport(
        export_schema_version=EXPORT_SCHEMA_VERSION,
        columns=list(EXPORT_FIELDS),
        rows=[{field: row.get(field) for field in EXPORT_FIELDS} for row in source],
        generated_at=utc_now(),
    )
