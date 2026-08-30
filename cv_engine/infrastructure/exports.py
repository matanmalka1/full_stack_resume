"""Writing a projected export to disk.

The application layer decides what an export contains; this module decides that
it is a CSV file beside a JSON sidecar naming its schema version, and writes
both. Storage layout is infrastructure's, which is why the writer is here and
the projection is not.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..application.maintenance import ApplicationExport, build_application_export
from ..application.ports import ApplicationStore
from ..application.queries import ApplicationListView

__all__ = ["export_csv", "write_export"]


def write_export(export: ApplicationExport, output: Path) -> Path:
    """Write one projected export as a CSV file beside its schema sidecar."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=export.columns)
        writer.writeheader()
        writer.writerows(export.rows)
    output.with_suffix(output.suffix + ".meta.json").write_text(
        json.dumps(export.metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def export_csv(applications: ApplicationListView | ApplicationStore, output: Path) -> Path:
    """Project applications onto the export schema and write them as CSV."""
    return write_export(build_application_export(applications), output)
