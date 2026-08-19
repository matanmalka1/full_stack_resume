"""Printing command results as JSON and exporting applications to CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..application.ports import ApplicationStore
from ..application.queries import ApplicationListView
from ..util import utc_now
from .context import CommandContext, _command


def _print(value: Any) -> None:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


EXPORT_SCHEMA_VERSION = "2.0"


def export_csv(applications: ApplicationListView | ApplicationStore, output: Path) -> Path:
    """Export applications with an explicit, versioned schema.

    The v1 export had no version marker, so a consumer could not tell which
    columns to expect. No such consumer was found in this repository, so the
    v2 export keeps the same columns and records the schema beside them rather
    than inventing a compatibility mode nothing asked for.
    """
    rows = (
        [item.model_dump(mode="json") for item in applications.items]
        if isinstance(applications, ApplicationListView)
        else applications.list_applications()
    )
    fields = [
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
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)
    output.with_suffix(output.suffix + ".meta.json").write_text(
        json.dumps(
            {
                "export_schema_version": EXPORT_SCHEMA_VERSION,
                "columns": fields,
                "row_count": len(rows),
                "generated_at": utc_now(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


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
