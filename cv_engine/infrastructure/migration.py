from __future__ import annotations

import csv
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .canonical_data import write_canonical_sources
from .db import Repository, connect
from ..domain.facts import FactStoreError
from .knowledge import read_fact_source
from ..util import canonical_json, sha256_bytes, sha256_file, sha256_text, utc_now


MIGRATION_NAMESPACE = uuid.UUID("7650f234-c480-4a9e-9c21-9d5142899a63")
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", "tmp"}
EXPECTED_COLUMNS = ["company", "role", "url", "cv_file", "status", "date_created", "date_sent", "notes"]


class MigrationSafetyError(RuntimeError):
    pass


MigrationTestRunner = Callable[[Path], Path]


def _content_hash(payload: dict[str, Any], *, hash_field: str, volatile_fields: tuple[str, ...] = ()) -> str:
    material = dict(payload)
    material.pop(hash_field, None)
    for field in volatile_fields:
        material.pop(field, None)
    return sha256_text(canonical_json(material))


def _inventory_hash(inventory: dict[str, Any]) -> str:
    return _content_hash(
        inventory,
        hash_field="inventory_hash",
        volatile_fields=("created_at",),
    )


def _report_hash(report: dict[str, Any]) -> str:
    return _content_hash(report, hash_field="report_hash")


def _seal_report(report: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(report)
    sealed["report_hash"] = _report_hash(sealed)
    return sealed


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationSafetyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise MigrationSafetyError(f"{label} must contain a JSON object")
    return value


def _snapshot_files(root: Path) -> list[Path]:
    result = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.parts[:2] == ("data", "snapshots"):
            continue
        if path.is_file() or path.is_symlink():
            result.append(path)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def _manifest_entry(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    if path.is_symlink():
        target = os.readlink(path)
        return {
            "path": relative,
            "kind": "symlink",
            "link_target": target,
            "size": len(target.encode("utf-8")),
            "sha256": sha256_text(target),
        }
    return {
        "path": relative,
        "kind": "file",
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def read_legacy_rows(root: Path) -> list[dict[str, str]]:
    path = root / "jobs" / "status.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise MigrationSafetyError(f"unexpected legacy CSV columns: {reader.fieldnames}")
        return list(reader)


def legacy_artifact_paths(root: Path, row: dict[str, str]) -> dict[str, Path]:
    company, role = row["company"], row["role"]
    company_root = root / "outputs" / company
    return {
        "job_snapshot": company_root / "job-description" / f"{company}_{role}.md",
        "resume_markdown": company_root / "cv-drafts" / f"cv_{company}_{role}.md",
        "tailoring_notes": company_root / "cv-drafts" / f"cv_{company}_{role}.notes.md",
        "resume_html": company_root / "cv-html" / f"cv_{company}_{role}.html",
        "resume_pdf": root / row["cv_file"],
    }


def build_inventory(root: Path) -> dict[str, Any]:
    rows = read_legacy_rows(root)
    accounted: set[str] = set()
    applications = []
    problems = []
    for index, row in enumerate(rows, 2):
        paths = legacy_artifact_paths(root, row)
        artifact_data = []
        for kind, path in paths.items():
            if not path.is_file():
                problems.append(f"row {index} missing {kind}: {path.relative_to(root)}")
                continue
            relative = path.relative_to(root).as_posix()
            accounted.add(relative)
            artifact_data.append({
                "type": kind,
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })
        applications.append({"csv_row": index, "row": row, "artifacts": artifact_data})

    base_paths = [
        root / "outputs/base/cv-drafts/cv_base_full-stack-developer.md",
        root / "outputs/base/cv-html/cv_base_full-stack-developer.html",
        root / "outputs/base/cv-pdf/full-stack-developer/Matan Malka - Full Stack Developer.pdf",
    ]
    base_artifacts = []
    for path in base_paths:
        if not path.is_file():
            problems.append(f"missing base historical artifact: {path.relative_to(root)}")
            continue
        relative = path.relative_to(root).as_posix()
        accounted.add(relative)
        base_artifacts.append({"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)})

    output_files = {
        path.relative_to(root).as_posix()
        for path in (root / "outputs").rglob("*")
        if path.is_file() and path.name not in {".DS_Store", ".gitkeep"}
    }
    unaccounted = sorted(output_files - accounted)
    if unaccounted:
        problems.extend(f"unaccounted output artifact: {path}" for path in unaccounted)
    duplicates = []
    seen_keys: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["company"].casefold(), row["role"].casefold())
        if key in seen_keys:
            duplicates.append(f"{row['company']} / {row['role']}")
        seen_keys.add(key)

    inventory = {
        "schema_version": "1.0.0",
        "created_at": utc_now(),
        "legacy_csv": "jobs/status.csv",
        "legacy_row_count": len(rows),
        "legacy_application_artifact_count": sum(len(app["artifacts"]) for app in applications),
        "base_artifact_count": len(base_artifacts),
        "legacy_output_file_count": len(output_files),
        "applications": applications,
        "base_artifacts": base_artifacts,
        "known_anomalies": [
            "CodeValue Sales is a documented off-pipeline artifact and fails the legacy Development validator.",
            "Helfy Markdown uses a legacy layout and fails the legacy Development validator.",
            "The base artifact set is not an application and has no CSV row.",
            "Legacy Pcom claims may be stale and are preserved only as historical outputs.",
        ],
        "duplicate_application_keys": duplicates,
        "unaccounted_output_files": unaccounted,
        "problems": problems,
    }
    inventory["inventory_hash"] = _inventory_hash(inventory)
    return inventory


def write_inventory(root: Path) -> Path:
    target = root / "data" / "migration" / "inventory.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(root)
    target.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if inventory["problems"]:
        raise MigrationSafetyError("inventory failed; see data/migration/inventory.json")
    return target


def create_snapshot(root: Path) -> Path:
    inventory_path = write_inventory(root)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if inventory["problems"] or inventory["unaccounted_output_files"]:
        raise MigrationSafetyError("cannot snapshot an incomplete inventory")
    snapshot_id = utc_now().replace(":", "").replace("+00:00", "Z").replace("-", "")
    target = root / "data" / "snapshots" / snapshot_id
    if target.exists():
        raise MigrationSafetyError(f"snapshot already exists: {target}")
    files = _snapshot_files(root)
    entries = [_manifest_entry(root, path) for path in files]
    manifest = {
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "created_at": utc_now(),
        "inventory_hash": inventory["inventory_hash"],
        "file_count": len(entries),
        "entries": entries,
    }
    manifest["manifest_hash"] = sha256_text(canonical_json(manifest))
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(root / "docs" / "v1-migration-restore.md", target / "RESTORE.md")
    archive = target / "repository.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in files:
            tar.add(path, arcname=path.relative_to(root), recursive=False)
    verification = verify_snapshot(target)
    (target / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not verification["passed"]:
        raise MigrationSafetyError(f"snapshot verification failed: {target}")
    return target


def _safe_extract(tar: tarfile.TarFile, target: Path) -> None:
    target_resolved = target.resolve()
    for member in tar.getmembers():
        member_path = (target / member.name).resolve()
        if member_path != target_resolved and target_resolved not in member_path.parents:
            raise MigrationSafetyError(f"unsafe archive member: {member.name}")
        if member.issym() and (Path(member.linkname).is_absolute() or ".." in Path(member.linkname).parts):
            raise MigrationSafetyError(f"unsafe archive symlink: {member.name}")
    tar.extractall(target, filter="data")


def verify_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    manifest_path = snapshot_dir / "manifest.json"
    archive_path = snapshot_dir / "repository.tar.gz"
    restore_path = snapshot_dir / "RESTORE.md"
    problems = []
    if not manifest_path.is_file() or not archive_path.is_file() or not restore_path.is_file():
        return {"passed": False, "problems": ["snapshot is missing manifest, archive, or restore instructions"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = manifest.pop("manifest_hash")
    actual_hash = sha256_text(canonical_json(manifest))
    manifest["manifest_hash"] = expected_hash
    if actual_hash != expected_hash:
        problems.append("manifest hash mismatch")
    with tempfile.TemporaryDirectory(prefix="cv-restore-") as directory:
        restored = Path(directory)
        with tarfile.open(archive_path, "r:gz") as tar:
            _safe_extract(tar, restored)
        for entry in manifest["entries"]:
            path = restored / entry["path"]
            if entry["kind"] == "symlink":
                if not path.is_symlink() or os.readlink(path) != entry["link_target"]:
                    problems.append(f"symlink mismatch: {entry['path']}")
            elif not path.is_file():
                problems.append(f"missing restored file: {entry['path']}")
            elif path.stat().st_size != entry["size"] or sha256_file(path) != entry["sha256"]:
                problems.append(f"restored file mismatch: {entry['path']}")
    return {
        "passed": not problems,
        "verified_at": utc_now(),
        "snapshot_id": manifest["snapshot_id"],
        "manifest_hash": expected_hash,
        "inventory_hash": manifest.get("inventory_hash"),
        "archive_sha256": sha256_file(archive_path),
        "file_count": manifest["file_count"],
        "restore_instructions": "RESTORE.md",
        "problems": problems,
    }


def run_migration_tests(root: Path) -> Path:
    command = [str(root / ".venv" / "bin" / "python") if (root / ".venv/bin/python").is_file() else "python3", "-m", "pytest", "tests/test_migration.py", "-q"]
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=180)
    report = _seal_report({
        "passed": completed.returncode == 0,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "created_at": utc_now(),
    })
    target = root / "data/migration/migration-tests.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise MigrationSafetyError("migration tests failed")
    return target


def _deterministic_id(kind: str, *parts: str) -> str:
    return str(uuid.uuid5(MIGRATION_NAMESPACE, ":".join((kind, *parts))))


def migrate_legacy_state(source_root: Path, target_root: Path, *, dry_run: bool) -> dict[str, Any]:
    inventory = build_inventory(source_root)
    if inventory["problems"]:
        raise MigrationSafetyError(f"cannot migrate incomplete inventory: {inventory['problems']}")
    db_path = target_root / "data" / "applications.sqlite3"
    if db_path.exists():
        raise MigrationSafetyError(f"refusing to overwrite database: {db_path}")
    if any((target_root / "base" / name).exists() for name in ("common.md", "sales.md", "development.md", "situational_skills.md")):
        raise MigrationSafetyError("refusing to overwrite existing modular fact sources")
    write_canonical_sources(target_root / "base")
    repository = Repository(db_path)
    rows = read_legacy_rows(source_root)
    migrated_artifacts = 0
    for row in rows:
        company, role = row["company"], row["role"]
        paths = legacy_artifact_paths(source_root, row)
        snapshot_text = paths["job_snapshot"].read_text(encoding="utf-8")
        app_id = _deterministic_id("application", company, role)
        snap_id = _deterministic_id("snapshot", company, role)
        repository.create_application(
            company=company,
            target_role=role,
            original_job_text=snapshot_text,
            source_url=row["url"] or None,
            source="legacy-csv",
            notes=row["notes"],
            application_id=app_id,
            snapshot_id=snap_id,
            captured_at=f"{row['date_created']}T00:00:00+00:00",
            source_metadata={"legacy_csv_row": row, "original_path": paths["job_snapshot"].relative_to(source_root).as_posix()},
        )
        if row["status"] == "sent":
            with repository.transaction() as connection:
                connection.execute(
                    "UPDATE applications SET current_status='applied', last_contact_date=?, updated_at=? WHERE id=?",
                    (row["date_sent"] or None, utc_now(), app_id),
                )
                connection.execute(
                    "INSERT INTO status_history(application_id, from_status, to_status, changed_at, reason) VALUES(?, 'saved', 'applied', ?, 'legacy sent mapped to applied')",
                    (app_id, f"{row['date_sent']}T00:00:00+00:00"),
                )
        elif row["status"] == "draft":
            repository.transition_status(app_id, "preparing", "legacy draft mapped to preparing; v1 ready checks not previously run")
        else:
            raise MigrationSafetyError(f"no deterministic mapping for legacy status {row['status']!r}")
        for artifact_type, path in paths.items():
            relative = path.relative_to(source_root).as_posix()
            repository.register_artifact_version(
                app_id,
                artifact_type,
                f"legacy-{artifact_type}",
                relative,
                sha256_file(path),
                "migrated-historical",
                job_snapshot_id=snap_id,
                metadata={"immutable": True, "legacy": True},
                submitted_at=(f"{row['date_sent']}T00:00:00+00:00" if row["status"] == "sent" else None),
            )
            migrated_artifacts += 1
    for artifact in inventory["base_artifacts"]:
        path = source_root / artifact["path"]
        artifact_type = "base_" + path.suffix.lstrip(".")
        repository.register_artifact_version(
            None,
            artifact_type,
            "legacy-base",
            artifact["path"],
            artifact["sha256"],
            "migrated-historical",
            metadata={"immutable": True, "legacy": True, "not_an_application": True},
        )
        migrated_artifacts += 1
    problems = repository.integrity_check()
    with connect(db_path) as connection:
        app_count = connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        snapshot_count = connection.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0]
        artifact_count = connection.execute("SELECT COUNT(*) FROM artifact_versions").fetchone()[0]
    if app_count != len(rows):
        problems.append(f"application count {app_count} != legacy rows {len(rows)}")
    if snapshot_count != len(rows):
        problems.append(f"snapshot count {snapshot_count} != legacy rows {len(rows)}")
    expected_artifacts = inventory["legacy_application_artifact_count"] + inventory["base_artifact_count"]
    if artifact_count != expected_artifacts or migrated_artifacts != expected_artifacts:
        problems.append(f"artifact count mismatch: db={artifact_count}, migrated={migrated_artifacts}, expected={expected_artifacts}")
    return {
        "passed": not problems,
        "dry_run": dry_run,
        "application_count": app_count,
        "job_snapshot_count": snapshot_count,
        "artifact_version_count": artifact_count,
        "expected_artifact_count": expected_artifacts,
        "inventory_hash": inventory["inventory_hash"],
        "database": db_path.relative_to(target_root).as_posix(),
        "problems": problems,
    }


DRY_RUN_EVIDENCE_FIELDS = (
    "passed",
    "dry_run",
    "application_count",
    "job_snapshot_count",
    "artifact_version_count",
    "expected_artifact_count",
    "inventory_hash",
    "database",
    "problems",
    "snapshot_id",
    "manifest_hash",
)


def _execute_snapshot_dry_run(snapshot_dir: Path, verification: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cv-migration-dry-run-") as directory:
        restored = Path(directory) / "source"
        restored.mkdir()
        with tarfile.open(snapshot_dir / "repository.tar.gz", "r:gz") as tar:
            _safe_extract(tar, restored)
        target = Path(directory) / "target"
        shutil.copytree(restored, target, symlinks=True)
        db = target / "data/applications.sqlite3"
        if db.exists():
            db.unlink()
        for name in ("common.md", "sales.md", "development.md", "situational_skills.md"):
            path = target / "base" / name
            if path.exists():
                path.unlink()
        report = migrate_legacy_state(restored, target, dry_run=True)
    report.update({
        "snapshot_id": verification["snapshot_id"],
        "manifest_hash": verification["manifest_hash"],
    })
    return report


def dry_run_migration(root: Path, snapshot_dir: Path) -> Path:
    verification = verify_snapshot(snapshot_dir)
    if not verification["passed"]:
        raise MigrationSafetyError("cannot dry-run an unverified snapshot")
    report = _execute_snapshot_dry_run(snapshot_dir, verification)
    report["created_at"] = utc_now()
    report = _seal_report(report)
    output = root / "data/migration/dry-run.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise MigrationSafetyError("dry-run migration failed")
    return output


def _report_integrity_problems(report: dict[str, Any], label: str) -> list[str]:
    expected = report.get("report_hash")
    if not isinstance(expected, str) or expected != _report_hash(report):
        return [f"{label} report hash mismatch"]
    return []


def _dry_run_fingerprint(report: dict[str, Any]) -> dict[str, Any]:
    return {field: report.get(field) for field in DRY_RUN_EVIDENCE_FIELDS}


def migration_gate(
    root: Path,
    snapshot_dir: Path,
    *,
    migration_test_runner: MigrationTestRunner | None = None,
) -> dict[str, Any]:
    inventory_path = root / "data/migration/inventory.json"
    tests_path = root / "data/migration/migration-tests.json"
    dry_run_path = root / "data/migration/dry-run.json"
    if not all(path.is_file() for path in (inventory_path, tests_path, dry_run_path)):
        raise MigrationSafetyError("inventory, migration tests, and dry-run reports are all required")
    inventory = _load_json(inventory_path, "inventory report")
    tests = _load_json(tests_path, "migration-test report")
    dry_run = _load_json(dry_run_path, "dry-run report")
    snapshot = verify_snapshot(snapshot_dir)
    problems = []
    if inventory.get("inventory_hash") != _inventory_hash(inventory):
        problems.append("inventory report hash mismatch")
    if inventory.get("problems") or inventory.get("unaccounted_output_files"):
        problems.append("inventory is incomplete")
    problems.extend(_report_integrity_problems(tests, "migration-test"))
    if tests.get("passed") is not True or tests.get("returncode") != 0:
        problems.append("migration tests failed")
    problems.extend(_report_integrity_problems(dry_run, "dry-run"))
    if dry_run.get("passed") is not True or dry_run.get("problems"):
        problems.append("dry-run migration failed")
    if not snapshot.get("passed"):
        problems.append("snapshot restore verification failed")
    if (
        dry_run.get("snapshot_id") != snapshot.get("snapshot_id")
        or dry_run.get("manifest_hash") != snapshot.get("manifest_hash")
    ):
        problems.append("dry-run was not performed against this snapshot")
    if dry_run.get("inventory_hash") != inventory.get("inventory_hash"):
        problems.append("inventory changed after dry-run")

    try:
        live_inventory = build_inventory(root)
    except (OSError, MigrationSafetyError, KeyError, ValueError) as exc:
        live_inventory = {}
        problems.append(f"cannot rebuild live inventory: {exc}")
    else:
        if live_inventory.get("problems") or live_inventory.get("unaccounted_output_files"):
            problems.append("live inventory is incomplete")
        if live_inventory.get("inventory_hash") != inventory.get("inventory_hash"):
            problems.append("live inventory does not match the recorded inventory")
        if live_inventory.get("inventory_hash") != snapshot.get("inventory_hash"):
            problems.append("live inventory does not match the verified snapshot")

    fresh_tests: dict[str, Any] = {}
    try:
        runner = migration_test_runner or run_migration_tests
        fresh_tests_path = runner(root)
        fresh_tests = _load_json(fresh_tests_path, "fresh migration-test report")
    except (OSError, subprocess.SubprocessError, MigrationSafetyError) as exc:
        problems.append(f"fresh migration tests could not run: {exc}")
    else:
        problems.extend(_report_integrity_problems(fresh_tests, "fresh migration-test"))
        if fresh_tests.get("passed") is not True or fresh_tests.get("returncode") != 0:
            problems.append("fresh migration tests failed")

    fresh_dry_run: dict[str, Any] = {}
    if snapshot.get("passed"):
        try:
            fresh_dry_run = _execute_snapshot_dry_run(snapshot_dir, snapshot)
        except (OSError, MigrationSafetyError, KeyError, ValueError, sqlite3.Error, tarfile.TarError) as exc:
            problems.append(f"fresh snapshot dry-run failed: {exc}")
        else:
            if not fresh_dry_run.get("passed") or fresh_dry_run.get("problems"):
                problems.append("fresh snapshot dry-run did not pass")
            if _dry_run_fingerprint(fresh_dry_run) != _dry_run_fingerprint(dry_run):
                problems.append("stored dry-run report does not match a fresh snapshot dry-run")
    return {
        "passed": not problems,
        "snapshot_id": snapshot.get("snapshot_id"),
        "manifest_hash": snapshot.get("manifest_hash"),
        "inventory_hash": live_inventory.get("inventory_hash"),
        "dry_run_report_hash": dry_run.get("report_hash"),
        "migration_test_report_hash": fresh_tests.get("report_hash"),
        "legacy_row_count": live_inventory.get("legacy_row_count"),
        "expected_artifact_count": fresh_dry_run.get("expected_artifact_count"),
        "problems": problems,
    }


def apply_migration(
    root: Path,
    snapshot_dir: Path,
    *,
    migration_test_runner: MigrationTestRunner | None = None,
) -> Path:
    gate = migration_gate(root, snapshot_dir, migration_test_runner=migration_test_runner)
    if not gate["passed"]:
        raise MigrationSafetyError(f"migration gate failed: {gate['problems']}")
    final_db = root / "data/applications.sqlite3"
    final_report = root / "data/migration/live-migration.json"
    final_facts = [root / "base" / name for name in ("common.md", "sales.md", "development.md", "situational_skills.md")]
    if final_db.exists() or final_report.exists() or any(path.exists() for path in final_facts):
        raise MigrationSafetyError("live migration targets already exist; refusing to overwrite")

    staging = root / "data" / "migration" / f"staging-{uuid.uuid4()}"
    staging.mkdir(parents=True)
    moved: list[tuple[Path, Path]] = []
    try:
        immediate_inventory = build_inventory(root)
        if immediate_inventory["problems"] or immediate_inventory["inventory_hash"] != gate["inventory_hash"]:
            raise MigrationSafetyError("live inventory changed after the migration gate")
        report = migrate_legacy_state(root, staging, dry_run=False)
        if not report["passed"]:
            raise MigrationSafetyError(f"staged live migration reconciliation failed: {report['problems']}")
        if report["inventory_hash"] != gate["inventory_hash"]:
            raise MigrationSafetyError("live inventory changed during staged migration")
        report["gate"] = gate
        report["created_at"] = utc_now()
        report = _seal_report(report)
        staged_db = staging / "data/applications.sqlite3"
        repository = Repository(staged_db)
        with repository.transaction() as connection:
            connection.execute(
                "INSERT INTO migration_runs(id, snapshot_id, manifest_hash, dry_run_report_hash, row_count, artifact_count, report_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), gate["snapshot_id"], gate["manifest_hash"], gate["dry_run_report_hash"],
                    gate["legacy_row_count"], gate["expected_artifact_count"], canonical_json(report), utc_now(),
                ),
            )
        with connect(staged_db) as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        staged_report = staging / "live-migration.json"
        staged_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sources = [staging / "base" / path.name for path in final_facts]
        sources.extend([staged_db, staged_report])
        destinations = [*final_facts, final_db, final_report]
        for source, destination in zip(sources, destinations, strict=True):
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
            moved.append((source, destination))
    except Exception:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                destination.replace(source)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return final_report


FACT_SOURCE_NAMES = ("common.md", "sales.md", "development.md", "situational_skills.md")


def _read_only_rows(
    database: Path,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(query, parameters)]
    finally:
        connection.close()


def _semantic_migration_state(database: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        "applications": _read_only_rows(database, """
            SELECT id, company, target_role, normalized_role, source_url, language, track, profile,
                   emphasis, classification_confidence, fit_level, current_status, last_contact_date,
                   next_action, next_action_date, notes, source, created_at
            FROM applications WHERE source='legacy-csv' ORDER BY id
        """),
        "job_snapshots": _read_only_rows(database, """
            SELECT js.id, js.application_id, js.version_number, js.original_text, js.source_url,
                   js.captured_at, js.source_metadata_json, js.content_hash, js.prior_snapshot_id
            FROM job_snapshots js JOIN applications a ON a.id=js.application_id
            WHERE a.source='legacy-csv' ORDER BY js.id
        """),
        "status_history": _read_only_rows(database, """
            SELECT sh.application_id, sh.from_status, sh.to_status, sh.reason
            FROM status_history sh JOIN applications a ON a.id=sh.application_id
            WHERE a.source='legacy-csv'
            ORDER BY sh.application_id, sh.id
        """),
        "artifact_versions": _read_only_rows(database, """
            SELECT a.application_id, a.artifact_type, a.logical_name, av.version_number,
                   av.lifecycle_status, av.path, av.content_hash, av.approved_at, av.submitted_at,
                   av.track, av.profile, av.emphasis, av.facts_version, av.job_snapshot_id,
                   av.metadata_json
            FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id
            WHERE a.logical_name LIKE 'legacy-%'
            ORDER BY a.application_id, a.artifact_type, a.logical_name, av.version_number
        """),
    }


def _fact_source_baseline(name: str, live_path: Path, expected_path: Path) -> tuple[list[str], list[str]]:
    """Compare one live fact source against the migration's expected output.

    This is a fact-level comparison rather than a file hash because the fact
    lifecycle legitimately rewrites these files after migration: creating a
    pending fact or promoting one to canonical changes the bytes without
    touching anything migration produced. What migration safety requires is
    that every migrated fact still exists, unchanged, in the same canonical
    source file. Facts added afterwards are reported, never a failure.
    """
    try:
        live = {fact.fact_id: fact.model_dump(mode="json") for fact in read_fact_source(live_path).facts}
    except FactStoreError as exc:
        return [f"canonical fact source is unreadable: base/{name} ({exc})"], []
    baseline = {fact.fact_id: fact.model_dump(mode="json") for fact in read_fact_source(expected_path).facts}
    problems = []
    for fact_id, payload in baseline.items():
        if fact_id not in live:
            problems.append(f"migrated fact is missing from base/{name}: {fact_id}")
        elif live[fact_id] != payload:
            problems.append(f"migrated fact changed in base/{name}: {fact_id}")
    return problems, sorted(set(live) - set(baseline))


def retrospective_verify_migration(root: Path, snapshot_dir: Path) -> dict[str, Any]:
    snapshot = verify_snapshot(snapshot_dir)
    problems: list[str] = []
    live_database = root / "data/applications.sqlite3"
    if not snapshot.get("passed"):
        problems.append("pre-migration snapshot verification failed")
    if not live_database.is_file():
        problems.append("live migrated database is missing")
    for name in FACT_SOURCE_NAMES:
        if not (root / "base" / name).is_file():
            problems.append(f"live canonical fact source is missing: base/{name}")
    if problems:
        return _seal_report({
            "schema_version": "1.0.0",
            "passed": False,
            "snapshot_id": snapshot.get("snapshot_id"),
            "problems": problems,
        })

    with tempfile.TemporaryDirectory(prefix="cv-retrospective-verification-") as directory:
        temporary = Path(directory)
        restored = temporary / "restored"
        restored.mkdir()
        with tarfile.open(snapshot_dir / "repository.tar.gz", "r:gz") as tar:
            _safe_extract(tar, restored)
        expected = temporary / "expected"
        expected.mkdir()
        migration_report = migrate_legacy_state(restored, expected, dry_run=True)
        if not migration_report["passed"]:
            problems.append(f"current migration failed on restored snapshot: {migration_report['problems']}")

        expected_database = expected / "data/applications.sqlite3"
        live_state = _semantic_migration_state(live_database)
        expected_state = _semantic_migration_state(expected_database)
        semantic_counts: dict[str, int] = {}
        semantic_hashes: dict[str, str] = {}
        for group, expected_rows in expected_state.items():
            live_rows = live_state[group]
            semantic_counts[group] = len(live_rows)
            semantic_hashes[group] = sha256_text(canonical_json(live_rows))
            if live_rows != expected_rows:
                problems.append(
                    f"live {group} semantics differ from current migration output "
                    f"(live={len(live_rows)}, expected={len(expected_rows)})"
                )

        fact_hashes: dict[str, str] = {}
        post_migration_facts: dict[str, list[str]] = {}
        for name in FACT_SOURCE_NAMES:
            live_path = root / "base" / name
            fact_hashes[name] = sha256_file(live_path)
            differences, added = _fact_source_baseline(name, live_path, expected / "base" / name)
            problems.extend(differences)
            if added:
                post_migration_facts[name] = added

        expected_artifacts = expected_state["artifact_versions"]
        artifact_hashes_checked = 0
        for artifact in expected_artifacts:
            path = root / artifact["path"]
            if not path.is_file():
                problems.append(f"live historical artifact is missing: {artifact['path']}")
            elif sha256_file(path) != artifact["content_hash"]:
                problems.append(f"live historical artifact hash mismatch: {artifact['path']}")
            else:
                artifact_hashes_checked += 1

        integrity = _read_only_rows(live_database, "PRAGMA integrity_check")
        foreign_keys = _read_only_rows(live_database, "PRAGMA foreign_key_check")
        if integrity != [{"integrity_check": "ok"}]:
            problems.append(f"live SQLite integrity check failed: {integrity}")
        if foreign_keys:
            problems.append(f"live SQLite foreign-key check failed: {foreign_keys}")

        matching_runs = _read_only_rows(
            live_database,
            "SELECT snapshot_id, manifest_hash, row_count, artifact_count FROM migration_runs "
            "WHERE snapshot_id=?",
            (snapshot["snapshot_id"],),
        )
        if len(matching_runs) != 1:
            problems.append(f"expected one live migration run for snapshot, found {len(matching_runs)}")
        else:
            run = matching_runs[0]
            if run["manifest_hash"] != snapshot.get("manifest_hash"):
                problems.append("live migration run manifest hash does not match the verified snapshot")
            if run["row_count"] != migration_report["application_count"]:
                problems.append("live migration run row count differs from current migration output")
            if run["artifact_count"] != migration_report["artifact_version_count"]:
                problems.append("live migration run artifact count differs from current migration output")

    return _seal_report({
        "schema_version": "1.0.0",
        "passed": not problems,
        "snapshot_id": snapshot.get("snapshot_id"),
        "manifest_hash": snapshot.get("manifest_hash"),
        "snapshot_archive_sha256": snapshot.get("archive_sha256"),
        "semantic_counts": semantic_counts,
        "semantic_hashes": semantic_hashes,
        "canonical_fact_hashes": fact_hashes,
        "post_migration_facts": post_migration_facts,
        "artifact_hashes_checked": artifact_hashes_checked,
        "live_database": live_database.relative_to(root).as_posix(),
        "problems": problems,
    })


def reconcile_migration(root: Path) -> dict[str, Any]:
    db_path = root / "data/applications.sqlite3"
    if not db_path.is_file():
        return {"passed": False, "problems": ["database does not exist"]}
    repository = Repository(db_path)
    problems = repository.integrity_check()
    inventory = build_inventory(root)
    with connect(db_path) as connection:
        applications = connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        snapshots = connection.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0]
        versions = connection.execute("SELECT path, content_hash FROM artifact_versions").fetchall()
        migration_runs = connection.execute("SELECT COUNT(*) FROM migration_runs").fetchone()[0]
    for row in versions:
        path = root / row["path"]
        if not path.is_file():
            problems.append(f"missing artifact: {row['path']}")
        elif sha256_file(path) != row["content_hash"]:
            problems.append(f"artifact hash mismatch: {row['path']}")
    expected_versions = inventory["legacy_application_artifact_count"] + inventory["base_artifact_count"]
    if applications != inventory["legacy_row_count"]:
        problems.append("application count does not match inventory")
    if snapshots != inventory["legacy_row_count"]:
        problems.append("job snapshot count does not match inventory")
    if len(versions) != expected_versions:
        problems.append(f"artifact version count {len(versions)} != expected {expected_versions}")
    if migration_runs != 1:
        problems.append(f"expected one migration run, found {migration_runs}")
    return {
        "passed": not problems,
        "application_count": applications,
        "job_snapshot_count": snapshots,
        "artifact_version_count": len(versions),
        "migration_run_count": migration_runs,
        "problems": problems,
    }
