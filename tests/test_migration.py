from __future__ import annotations

import json
from pathlib import Path

import pytest

from cv_engine.infrastructure import migration
from cv_engine.infrastructure.persistence import connect
from cv_engine.infrastructure.migration import (
    MigrationSafetyError,
    apply_migration,
    build_inventory,
    create_snapshot,
    migration_gate,
    migrate_legacy_state,
    retrospective_verify_migration,
    verify_snapshot,
)
from cv_engine.util import canonical_json, sha256_file, sha256_text
from cv_engine.runtime.composition import build_services
from cv_engine.runtime.workspace import load_workspace
from helpers import passing_migration_test_runner as _passing_test_runner


SOURCE_ROOT = Path(__file__).resolve().parent.parent


def test_live_legacy_inventory_is_fully_accounted() -> None:
    inventory = build_inventory(SOURCE_ROOT)
    assert inventory["legacy_row_count"] == 22
    assert inventory["legacy_application_artifact_count"] == 110
    assert inventory["base_artifact_count"] == 3
    assert inventory["legacy_output_file_count"] == 113
    assert inventory["problems"] == []
    assert inventory["unaccounted_output_files"] == []


def test_snapshot_restore_and_migration_preserve_rows_and_artifacts(
    tmp_path: Path, legacy_repo: Path
) -> None:
    source = legacy_repo
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
        snapshots = connection.execute(
            "SELECT payload_path, source_hash, source_metadata_json FROM job_snapshots"
        ).fetchall()
    assert statuses == {"alpha": "preparing", "beta": "applied"}
    assert len(paths) == 13
    for snapshot_row in snapshots:
        payload_path = target / snapshot_row["payload_path"]
        metadata = json.loads(snapshot_row["source_metadata_json"])
        assert payload_path.read_bytes() == (source / metadata["original_path"]).read_bytes()
        assert sha256_file(payload_path) == snapshot_row["source_hash"]
    assert (target / "base/sales.md").is_file()
    sales = (target / "base/sales.md").read_text(encoding="utf-8")
    assert "a team of 2-3 sales representatives" in sales
    assert "30% YoY" not in sales


def test_migration_gate_recomputes_all_authoritative_evidence(migration_gate_repo) -> None:
    root, snapshot = migration_gate_repo

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert gate["passed"], gate
    assert gate["inventory_hash"] == verify_snapshot(snapshot)["inventory_hash"]
    assert gate["migration_test_report_hash"]


def test_migration_gate_rejects_live_data_drift_after_dry_run(migration_gate_repo) -> None:
    root, snapshot = migration_gate_repo
    artifact = root / "outputs/alpha/cv-drafts/cv_alpha_account-manager.md"
    artifact.write_text("changed after dry-run\n", encoding="utf-8")

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert not gate["passed"]
    assert "live inventory does not match the recorded inventory" in gate["problems"]
    assert "live inventory does not match the verified snapshot" in gate["problems"]


def test_migration_gate_binds_inventory_to_snapshot_manifest(migration_gate_repo) -> None:
    root, snapshot = migration_gate_repo
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["inventory_hash"] = "0" * 64
    manifest.pop("manifest_hash")
    manifest["manifest_hash"] = sha256_text(canonical_json(manifest))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    gate = migration_gate(root, snapshot, migration_test_runner=_passing_test_runner)

    assert not gate["passed"]
    assert "live inventory does not match the verified snapshot" in gate["problems"]


def test_apply_rechecks_inventory_immediately_before_staging(
    migration_gate_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, snapshot = migration_gate_repo
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

    with pytest.raises(
        MigrationSafetyError, match="live inventory changed after the migration gate"
    ):
        apply_migration(root, snapshot, migration_test_runner=_passing_test_runner)


def test_retrospective_verification_reproduces_completed_migration(
    completed_migration_repo,
) -> None:
    root, snapshot = completed_migration_repo

    report = retrospective_verify_migration(root, snapshot)

    assert report["passed"], report
    assert report["semantic_counts"] == {
        "applications": 2,
        "job_snapshots": 2,
        "status_history": 4,
        "artifact_versions": 13,
    }
    with connect(root / "data/applications.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM selection_plans").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM working_drafts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM approved_revisions").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM artifact_versions WHERE revision_id IS NOT NULL"
            ).fetchone()[0]
            == 0
        )
    assert report["artifact_hashes_checked"] == 13


def test_retrospective_verification_detects_live_database_drift(completed_migration_repo) -> None:
    root, snapshot = completed_migration_repo
    with connect(root / "data/applications.sqlite3") as connection:
        connection.execute(
            "UPDATE applications SET notes='changed after migration' WHERE company='alpha'"
        )
        connection.commit()

    report = retrospective_verify_migration(root, snapshot)

    assert not report["passed"]
    assert any("applications semantics differ" in problem for problem in report["problems"])


def test_retrospective_verification_detects_fact_and_artifact_drift(
    completed_migration_repo,
) -> None:
    root, snapshot = completed_migration_repo
    (root / "base/sales.md").write_text("changed canonical facts\n", encoding="utf-8")
    artifact = root / "outputs/alpha/cv-drafts/cv_alpha_account-manager.md"
    artifact.write_text("changed historical artifact\n", encoding="utf-8")

    report = retrospective_verify_migration(root, snapshot)

    assert not report["passed"]
    assert any("base/sales.md" in problem for problem in report["problems"])
    assert any("historical artifact hash mismatch" in problem for problem in report["problems"])


def test_retrospective_verification_accepts_post_migration_lifecycle_facts(
    completed_migration_repo,
) -> None:
    """A fact added through the lifecycle is not migration drift.

    Migration safety requires that everything migration produced survives
    unchanged, not that the canonical sources are frozen: the pending ->
    confirmed -> canonical lifecycle writes to these files by design.
    """
    root, snapshot = completed_migration_repo
    knowledge = build_services(load_workspace(root)).knowledge_lifecycle
    knowledge.add_fact(
        "situational_skills.md",
        {
            "fact_id": "situational.post_migration_example",
            "meaning": "Used SQLite for local application state in a personal project.",
            "renderings": {"en": "Used SQLite for local application state in a personal project."},
            "tags": ["development", "situational", "databases"],
            "provenance": "post-migration lifecycle test",
            "resume_style": "bullet",
        },
    )
    knowledge.promote_fact(
        "situational.post_migration_example", "confirmed", explicitly_confirmed=True
    )
    knowledge.promote_fact(
        "situational.post_migration_example", "canonical", explicitly_confirmed=True
    )

    report = retrospective_verify_migration(root, snapshot)

    assert report["passed"], report["problems"]
    assert report["post_migration_facts"] == {
        "situational_skills.md": ["situational.post_migration_example"]
    }
