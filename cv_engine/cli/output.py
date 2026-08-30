"""Printing command results as JSON, and the export maintenance command.

The application layer decides what an export contains; this module decides
that the CLI's export is a CSV file with a JSON sidecar, and writes it.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..application.maintenance import (
    EXPORT_SCHEMA_VERSION,
    ApplicationExport,
    build_application_export,
)
from ..application.ports import ApplicationStore
from ..application.queries import ApplicationListView
from .context import CommandContext, _command


def _print(value: Any) -> None:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


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


@_command("export")
def _export(context: CommandContext) -> int:
    exported = export_csv(
        context.built_services.queries.list_applications(), context.args.output.resolve()
    )
    _print(
        {
            "csv": str(exported),
            "metadata": str(exported.with_suffix(exported.suffix + ".meta.json")),
            "export_schema_version": EXPORT_SCHEMA_VERSION,
        }
    )
    return 0
