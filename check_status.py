#!/usr/bin/env python3
"""
Reconcile jobs/status.csv against what is actually on disk.

Usage:
    python3 check_status.py

Checks, in order:
  1. every row has the expected columns and a non-empty company, role, status
  2. every row's cv_file path exists
  3. every draft on disk has a row in status.csv
  4. no two unresolved rows (status != sent) share a company and a similar role
  5. a row marked sent has a date_sent, and a row not sent does not

Exit code 0 if clean, 1 if anything needs attention. Nothing is ever modified:
this reports, it does not repair.

Python standard library only.
"""

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
STATUS = REPO / "jobs" / "status.csv"
OUTPUTS = REPO / "outputs"

EXPECTED_COLUMNS = ["company", "role", "url", "cv_file", "status",
                    "date_created", "date_sent", "notes"]

problems = []
notes = []


def slug(text):
    """Loose comparison key: 'AI Backend Engineer' and 'ai-backend-engineer' match."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def similar(a, b):
    sa, sb = slug(a), slug(b)
    if not sa or not sb:
        return False
    return sa == sb or sa in sb or sb in sa


def main():
    if not STATUS.is_file():
        print(f"status.csv not found: {STATUS}")
        return 1

    with STATUS.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)

    missing_cols = [c for c in EXPECTED_COLUMNS if c not in header]
    if missing_cols:
        problems.append(f"status.csv is missing columns: {', '.join(missing_cols)}")
        problems.append(f"  found header: {', '.join(header)}")
        print("FAIL: status.csv schema\n")
        print("\n".join(problems))
        return 1

    # 1 + 2 + 5: per-row checks
    for n, row in enumerate(rows, start=2):
        company = (row.get("company") or "").strip()
        role = (row.get("role") or "").strip()
        status = (row.get("status") or "").strip().lower()
        cv_file = (row.get("cv_file") or "").strip()
        date_sent = (row.get("date_sent") or "").strip()

        label = f"row {n} ({company or '?'} / {role or '?'})"

        if not company or not role:
            problems.append(f"{label}: company and role are both required")
        if not status:
            problems.append(f"{label}: empty status")

        if not cv_file:
            problems.append(f"{label}: empty cv_file")
        elif not (REPO / cv_file).exists():
            problems.append(f"{label}: cv_file does not exist on disk")
            problems.append(f"    {cv_file}")

        if status == "sent" and not date_sent:
            problems.append(f"{label}: status is sent but date_sent is empty")
        if status != "sent" and date_sent:
            problems.append(f"{label}: date_sent is filled but status is '{status}'")

    # 3: drafts on disk with no row
    for draft in sorted(OUTPUTS.glob("*/cv-drafts/cv_*.md")):
        if draft.name.endswith(".notes.md"):
            continue
        company = draft.parent.parent.name
        stem = draft.stem
        prefix = f"cv_{company}_"
        role = stem[len(prefix):] if stem.startswith(prefix) else ""
        if not role:
            problems.append("draft filename does not match cv_<company>_<role>.md")
            problems.append(f"    {draft.relative_to(REPO)}")
            continue
        matched = any(
            slug(company) == slug(r.get("company", "")) and similar(role, r.get("role", ""))
            for r in rows
        )
        if not matched:
            problems.append(f"draft on disk with no row in status.csv: {company} / {role}")
            problems.append(f"    {draft.relative_to(REPO)}")

    # 4: duplicate unresolved rows
    unresolved = [r for r in rows
                  if (r.get("status") or "").strip().lower() != "sent"]
    for i in range(len(unresolved)):
        for j in range(i + 1, len(unresolved)):
            a, b = unresolved[i], unresolved[j]
            if (slug(a.get("company", "")) == slug(b.get("company", ""))
                    and similar(a.get("role", ""), b.get("role", ""))):
                problems.append(
                    f"two unresolved drafts for the same company and a similar role: "
                    f"{a.get('company')} / {a.get('role')} and {b.get('role')}")
                problems.append(
                    "    resolve the duplicate before drafting again; preserve existing "
                    "historical artifacts")

    # orphan PDFs, reported as notes rather than failures
    for pdf in sorted(OUTPUTS.glob("*/cv-pdf/*.pdf")):
        notes.append(f"PDF sits directly in cv-pdf/ instead of cv-pdf/<role>/: "
                     f"{pdf.relative_to(REPO)}")

    if notes:
        print("Notes:")
        print("\n".join(f"  {x}" for x in notes))
        print()

    if problems:
        print(f"FAIL: {len(rows)} rows checked, issues found\n")
        print("\n".join(f"  {x}" if not x.startswith("    ") else x
                        for x in problems))
        return 1

    print(f"OK: {len(rows)} rows in status.csv, all consistent with disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
