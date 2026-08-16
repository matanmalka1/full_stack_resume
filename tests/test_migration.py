from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from cv_engine.db import connect
from cv_engine.migration import (
    build_inventory,
    create_snapshot,
    migrate_legacy_state,
    verify_snapshot,
)


SOURCE_ROOT = Path(__file__).resolve().parent.parent


def _legacy_fixture(root: Path) -> None:
    (root / "jobs").mkdir(parents=True)
    (root / "docs").mkdir()
    shutil.copy2(SOURCE_ROOT / "docs/v1-migration-restore.md", root / "docs/v1-migration-restore.md")
    rows = [
        ["alpha", "account-manager", "", "outputs/alpha/cv-pdf/account-manager/Matan Malka - Account Manager.pdf", "draft", "2026-01-01", "", ""],
        ["beta", "developer", "https://example.test/job", "outputs/beta/cv-pdf/developer/Matan Malka - Full Stack Developer.pdf", "sent", "2026-01-02", "2026-01-03", "submitted"],
    ]
    with (root / "jobs/status.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["company", "role", "url", "cv_file", "status", "date_created", "date_sent", "notes"])
        writer.writerows(rows)
    for company, role, *_rest in rows:
        paths = [
            root / f"outputs/{company}/job-description/{company}_{role}.md",
            root / f"outputs/{company}/cv-drafts/cv_{company}_{role}.md",
            root / f"outputs/{company}/cv-drafts/cv_{company}_{role}.notes.md",
            root / f"outputs/{company}/cv-html/cv_{company}_{role}.html",
            root / rows[[row[0] for row in rows].index(company)][3],
        ]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((f"historical {company} {role} {path.suffix}\n").encode())
    base_paths = [
        root / "outputs/base/cv-drafts/cv_base_full-stack-developer.md",
        root / "outputs/base/cv-html/cv_base_full-stack-developer.html",
        root / "outputs/base/cv-pdf/full-stack-developer/Matan Malka - Full Stack Developer.pdf",
    ]
    for path in base_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"historical base\n")


def test_live_legacy_inventory_is_fully_accounted() -> None:
    inventory = build_inventory(SOURCE_ROOT)
    assert inventory["legacy_row_count"] == 22
    assert inventory["legacy_application_artifact_count"] == 110
    assert inventory["base_artifact_count"] == 3
    assert inventory["legacy_output_file_count"] == 113
    assert inventory["problems"] == []
    assert inventory["unaccounted_output_files"] == []


def test_snapshot_restore_and_migration_preserve_rows_and_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    source.mkdir()
    _legacy_fixture(source)
    inventory = build_inventory(source)
    assert inventory["problems"] == []
    snapshot = create_snapshot(source)
    verification = verify_snapshot(snapshot)
    assert verification["passed"], verification

    target = tmp_path / "migrated"
    target.mkdir()
    report = migrate_legacy_state(source, target, dry_run=True)
    assert report["passed"], report
    assert report["application_count"] == 2
    assert report["artifact_version_count"] == 13
    with connect(target / "data/applications.sqlite3") as connection:
        statuses = dict(connection.execute("SELECT company, current_status FROM applications"))
        paths = connection.execute("SELECT path, content_hash FROM artifact_versions").fetchall()
    assert statuses == {"alpha": "preparing", "beta": "applied"}
    assert len(paths) == 13
    assert (target / "base/sales.md").is_file()
    sales = (target / "base/sales.md").read_text(encoding="utf-8")
    assert "approximately 2-3 Sales representatives" in sales
    assert "30% YoY" not in sales
