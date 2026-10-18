#!/usr/bin/env python3
"""Compare two live tailoring eval reports, case by case.

    python scripts/compare_evals.py tmp/evals/<old>.json tmp/evals/<new>.json

Reports come from `tests/evals/test_live_tailoring.py`. For every case in either
report, prints each metric's old value, new value, and the change; a case present in
only one report is listed as such. Standard library only, so it runs anywhere the
reports do.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

#: (label, path into a case) for every metric compared, in print order.
METRICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("analysis status", ("analysis_operation", "status")),
    ("draft status", ("draft_operation", "status")),
    ("models", ("models",)),
    ("reasoning efforts", ("reasoning_efforts",)),
    ("language", ("language",)),
    ("profile", ("profile",)),
    ("fit", ("fit",)),
    ("fit score", ("fit_score",)),
    ("requirements", ("requirements",)),
    ("injected requirements", ("injected_requirement_ids",)),
    ("mandatory recall", ("mandatory_recall",)),
    ("evidence lines", ("evidence_lines",)),
    ("withheld count", ("withheld_count",)),
    ("withheld rate", ("withheld_rate",)),
    ("reworded share", ("reworded_share",)),
    ("page fit", ("page_fit", "status")),
    ("pages", ("page_fit", "pages")),
    ("trimmed", ("page_fit", "trimmed")),
    ("budget violations", ("budget_violations",)),
    ("input tokens", ("input_tokens",)),
    ("output tokens", ("output_tokens",)),
    ("total tokens", ("total_tokens",)),
    ("cost usd", ("cost_usd",)),
)


def _read(case: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = case
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    if isinstance(value, list) and path[-1] in {"budget_violations", "injected_requirement_ids"}:
        return len(value)
    return value


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    return None


def _delta(old: Any, new: Any) -> str:
    before, after = _number(old), _number(new)
    if before is not None and after is not None:
        change = after - before
        if change == 0:
            return "="
        return f"{change:+}"
    return "=" if old == new else "changed"


def _show(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return ",".join(str(item) for item in value) or "-"
    return str(value)


def _versions(case: dict[str, Any]) -> str:
    versions = case.get("versions") or {}
    return "; ".join(
        f"{task} {item.get('task_contract_version')}/{item.get('prompt_version')}"
        for task, item in sorted(versions.items())
    )


def _cases(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {case["case"]: case for case in report.get("cases", [])}


def compare(old: dict[str, Any], new: dict[str, Any]) -> str:
    lines: list[str] = []
    before, after = _cases(old), _cases(new)
    for name in [*before, *(name for name in after if name not in before)]:
        lines.append(f"== {name}")
        if name not in after:
            lines.append("   only in the old report")
            continue
        if name not in before:
            lines.append("   only in the new report")
            continue
        rows = [("metric", "old", "new", "delta")]
        old_versions, new_versions = _versions(before[name]), _versions(after[name])
        rows.append(
            (
                "versions",
                old_versions or "-",
                new_versions or "-",
                "=" if old_versions == new_versions else "changed",
            )
        )
        for label, path in METRICS:
            old_value, new_value = _read(before[name], path), _read(after[name], path)
            rows.append((label, _show(old_value), _show(new_value), _delta(old_value, new_value)))
        widths = [max(len(row[index]) for row in rows) for index in range(4)]
        lines.extend(
            "   " + "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True))
            for row in rows
        )
    total_old, total_new = old.get("cost_usd"), new.get("cost_usd")
    lines.append(f"== total cost usd: {total_old} -> {total_new} ({_delta(total_old, total_new)})")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {Path(argv[0]).name} <old.json> <new.json>", file=sys.stderr)
        return 2
    old, new = (json.loads(Path(arg).read_text(encoding="utf-8")) for arg in argv[1:])
    print(compare(old, new))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
