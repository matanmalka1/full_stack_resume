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
from .ports import ApplicationStore, ReadinessRepository, SnapshotPayloadStore
from .queries import ApplicationListView

EXPORT_SCHEMA_VERSION = "2.0"


def reconcile_artifacts(
    payloads: SnapshotPayloadStore,
    repo: ReadinessRepository,
) -> dict[str, Any]:
    """Check database references and artifact hashes against stored evidence.

    Verification goes through the payload store rather than resolving each row
    to a local path and hashing the file. That path verified the local disk no
    matter which backend was configured, so it reported every artifact missing
    once storage moved off it - the same defect `verify_payload` was introduced
    to fix for Ready qualification, and a worse one here, because reconcile is
    the command that exists to report the truth about stored evidence.
    """
    problems = repo.integrity_check()
    checked = 0
    for row in repo.artifact_inventory():
        checked += 1
        verification = payloads.verify_payload(row["path"], row["content_hash"])
        if verification == "missing":
            problems.append(f"missing artifact: {row['path']}")
        elif verification == "tampered":
            problems.append(f"artifact hash mismatch: {row['path']}")
        elif verification == "unresolvable":
            # Distinct from absent: the reference itself does not name an
            # approved payload, which is a malformed row rather than a lost
            # file. Collapsing the two would hide which one happened.
            problems.append(f"unresolvable artifact reference: {row['path']}")
    return {"passed": not problems, "artifact_versions_checked": checked, "problems": problems}


EXPORT_FIELDS = [
    "id",
    "company",
    "target_role",
    "normalized_role",
    "source_url",
    "language",
    "track",
    "profile",
    "emphasis",
    "classification_confidence",
    "fit_level",
    "current_status",
    "last_contact_date",
    "next_action",
    "next_action_date",
    "notes",
    "source",
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


def build_application_export(
    applications: ApplicationListView | ApplicationStore,
) -> ApplicationExport:
    """Project applications onto the versioned export schema.

    The v1 export had no version marker, so a consumer could not tell which
    columns to expect. No such consumer was found in this repository, so the
    v2 export keeps the same columns and records the schema beside them rather
    than inventing a compatibility mode nothing asked for.
    """
    source = (
        [item.model_dump(mode="json") for item in applications.items]
        if isinstance(applications, ApplicationListView)
        else applications.list_applications()
    )
    return ApplicationExport(
        export_schema_version=EXPORT_SCHEMA_VERSION,
        columns=list(EXPORT_FIELDS),
        rows=[{field: row.get(field) for field in EXPORT_FIELDS} for row in source],
        generated_at=utc_now(),
    )
