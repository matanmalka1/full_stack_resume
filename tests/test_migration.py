from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from cv_engine import migration
from cv_engine.db import connect
from cv_engine.migration import (
    MigrationSafetyError,
    apply_migration,
    build_inventory,
    create_snapshot,
    dry_run_migration,
    migration_gate,
    migrate_legacy_state,
    verify_snapshot,
)
from cv_engine.util import canonical_json, sha256_text


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


def _seal_report(report: dict) -> dict:
    sealed = dict(report)
    sealed.pop("report_hash", None)
    sealed["report_hash"] = sha256_text(canonical_json(sealed))
    return sealed


def _write_passing_test_report(root: Path) -> Path:
    target = root / "data/migration/migration-tests.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    report = _seal_report({
        "passed": True,
        "command": ["python", "-m", "pytest", "tests/test_migration.py", "-q"],
        "returncode": 0,
        "stdout": "migration fixture passed",
        "stderr": "",
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


def _passing_test_runner(root: Path) -> Path:
    return root / "data/migration/migration-tests.json"


def _gate_fixture(root: Path) -> Path:
    _legacy_fixture(root)
    snapshot = create_snapshot(root)
    dry_run_migration(root, snapshot)
    _write_passing_test_report(root)
    return snapshot


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


def test_migration_gate_recomputes_all_authoritative_evidence(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    snapshot = _gate_fixture(root)

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert gate["passed"], gate
    assert gate["inventory_hash"] == verify_snapshot(snapshot)["inventory_hash"]
    assert gate["migration_test_report_hash"]


def test_migration_gate_rejects_forged_test_report_even_when_passed_is_true(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    snapshot = _gate_fixture(root)
    report_path = root / "data/migration/migration-tests.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update({"passed": True, "returncode": 99, "stdout": "forged"})
    report_path.write_text(json.dumps(_seal_report(report), indent=2) + "\n", encoding="utf-8")

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert not gate["passed"]
    assert "migration tests failed" in gate["problems"]


def test_migration_gate_rejects_stale_dry_run_with_a_valid_self_hash(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    snapshot = _gate_fixture(root)
    report_path = root / "data/migration/dry-run.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["application_count"] = 999
    report_path.write_text(json.dumps(_seal_report(report), indent=2) + "\n", encoding="utf-8")

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert not gate["passed"]
    assert "stored dry-run report does not match a fresh snapshot dry-run" in gate["problems"]


def test_migration_gate_rejects_live_data_drift_after_dry_run(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    snapshot = _gate_fixture(root)
    artifact = root / "outputs/alpha/cv-drafts/cv_alpha_account-manager.md"
    artifact.write_text("changed after dry-run\n", encoding="utf-8")

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert not gate["passed"]
    assert "live inventory does not match the recorded inventory" in gate["problems"]
    assert "live inventory does not match the verified snapshot" in gate["problems"]


def test_migration_gate_rejects_missing_legacy_status_csv(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    snapshot = _gate_fixture(root)
    (root / "jobs/status.csv").unlink()

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert not gate["passed"]
    assert any(problem.startswith("cannot rebuild live inventory") for problem in gate["problems"])


def test_migration_gate_binds_inventory_to_snapshot_manifest(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    snapshot = _gate_fixture(root)
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["inventory_hash"] = "0" * 64
    manifest.pop("manifest_hash")
    manifest["manifest_hash"] = sha256_text(canonical_json(manifest))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert not gate["passed"]
    assert "live inventory does not match the verified snapshot" in gate["problems"]


def test_apply_rechecks_inventory_immediately_before_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    snapshot = _gate_fixture(root)
    original_build_inventory = migration.build_inventory
    root_calls = 0

    def drift_before_second_live_inventory(candidate: Path) -> dict:
        nonlocal root_calls
        if candidate == root:
            root_calls += 1
            if root_calls == 2:
                artifact = root / "outputs/alpha/cv-drafts/cv_alpha_account-manager.md"
                artifact.write_text("changed between gate and staging\n", encoding="utf-8")
        return original_build_inventory(candidate)

    monkeypatch.setattr(migration, "build_inventory", drift_before_second_live_inventory)

    with pytest.raises(MigrationSafetyError, match="live inventory changed after the migration gate"):
        apply_migration(root, snapshot, migration_test_runner=_passing_test_runner)
