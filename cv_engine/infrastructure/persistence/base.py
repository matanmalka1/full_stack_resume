from __future__ import annotations

from typing import Any

from ...util import canonical_json


def json_text_record(row: Any, *fields: str) -> dict[str, Any]:
    """Serialize selected SQL JSON columns for repository read records."""
    record = dict(row)
    for field in fields:
        value = record[field]
        record[field] = None if value is None else canonical_json(value)
    return record
