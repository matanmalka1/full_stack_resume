"""Workspace identity, fail-closed guards, and config precedence.

These are the M1 foundations every later v2 command depends on: if a directory
can be opened without a marker, or a legacy v1 root can be written to, no later
safety property means anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import CliRun, run_cli

from cv_engine.infrastructure.persistence import connect, current_schema_version, initialize
from cv_engine.runtime.backup import BackupError, backup_workspace, restore_workspace
from cv_engine.runtime.composition import build_services
from cv_engine.runtime.config import CONFIG_NAME, resolve_config
from cv_engine.runtime.workspace import (
    MARKER_NAME,
    WorkspaceError,
    create_workspace,
    load_workspace,
)

SOURCE_ROOT = Path(__file__).resolve().parent.parent


# --- Workspace identity and roots ------------------------------------------


def test_created_workspace_round_trips_with_identity_and_roots(tmp_path: Path) -> None:
    created = create_workspace(tmp_path / "ws", purpose="development", data_class="copy")
    opened = load_workspace(tmp_path / "ws")

    assert opened.workspace_id == created.workspace_id
    assert opened.purpose == "development"
    assert opened.data_class == "copy"
    assert opened.knowledge_root == opened.root
    assert opened.state_root == opened.root / "data"
    assert opened.artifacts_root == opened.root / "artifacts"
    assert opened.temp_root == opened.root / "tmp"
    assert opened.logs_root == opened.root / "logs"
    for root in (opened.state_root, opened.artifacts_root, opened.temp_root, opened.logs_root):
        assert root.is_dir()
    first = opened.installation_id()
    assert first == load_workspace(opened.root).installation_id()
    assert first != opened.workspace_id

    workspace = create_workspace(
        tmp_path / "custom",
        roots={"artifacts_root": "payloads", "state_root": "state"},
    )
    assert workspace.artifacts_root == workspace.root / "payloads"
    assert workspace.state_root == workspace.root / "state"
    assert workspace.database_path == workspace.root / "state" / "applications.sqlite3"

    with pytest.raises(WorkspaceError, match="escapes the Workspace"):
        create_workspace(tmp_path / "escaped", roots={"artifacts_root": "../outside"})

    # A marker edited by hand is caught on the way in, not trusted.
    hand_edited = create_workspace(tmp_path / "hand-edited")
    marker = hand_edited.root / MARKER_NAME
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["roots"] = {"artifacts_root": "../outside"}
    marker.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(WorkspaceError, match="escapes the Workspace"):
        load_workspace(hand_edited.root)
    assert workspace.relative(workspace.artifacts_root / "a" / "b.pdf") == "payloads/a/b.pdf"
    with pytest.raises(WorkspaceError, match="outside the Workspace"):
        workspace.relative(Path("payloads/a/b.pdf"))
    with pytest.raises(WorkspaceError, match="outside the Workspace"):
        workspace.relative(tmp_path / "elsewhere.pdf")


# --- fail-closed guards -----------------------------------------------------


def test_workspace_markers_fail_closed_for_plain_legacy_invalid_and_reused_roots(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(WorkspaceError, match="no v2 Workspace marker"):
        load_workspace(plain)
    legacy = tmp_path / "legacy"
    (legacy / "jobs").mkdir(parents=True)
    (legacy / "jobs/status.csv").write_text("company,role\n", encoding="utf-8")

    with pytest.raises(WorkspaceError, match="is a legacy v1 root"):
        load_workspace(legacy)
    with pytest.raises(WorkspaceError, match="refusing to mark a legacy v1 root"):
        create_workspace(legacy)
    assert not (legacy / MARKER_NAME).exists()
    workspace = create_workspace(tmp_path / "ws")
    with pytest.raises(WorkspaceError, match="already exists"):
        create_workspace(workspace.root)
    marker = workspace.root / MARKER_NAME
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["workspace_version"] = 1
    marker.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(WorkspaceError, match="unsupported Workspace version 1"):
        load_workspace(workspace.root)
    (workspace.root / MARKER_NAME).write_text("{not json", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="unreadable Workspace marker"):
        load_workspace(workspace.root)
    with pytest.raises(WorkspaceError):
        build_services(load_workspace(plain))


def test_live_data_is_refused_outside_a_live_runtime(tmp_path: Path) -> None:
    for purpose in ("development", "test"):
        with pytest.raises(WorkspaceError, match="may not open live data"):
            create_workspace(tmp_path / purpose, purpose=purpose, data_class="live")
        live = create_workspace(tmp_path / f"{purpose}-live", purpose="live", data_class="live")
        marker = live.root / MARKER_NAME
        payload = json.loads(marker.read_text(encoding="utf-8"))
        payload["purpose"] = purpose
        marker.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(WorkspaceError, match="may not open live data"):
            load_workspace(live.root)


# --- configuration precedence ----------------------------------------------


def test_config_precedence_is_cli_then_env_then_workspace_then_default(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path / "ws")
    (workspace.root / CONFIG_NAME).write_text(
        json.dumps({"provider": "stored-provider", "model": "stored-model"}),
        encoding="utf-8",
    )

    resolved = resolve_config(
        cli={"provider": "cli-provider"},
        env={"CV_PROVIDER": "env-provider", "CV_MODEL": "env-model"},
        workspace_root=workspace.root,
    )
    assert (resolved.get("provider"), resolved.source("provider")) == ("cli-provider", "cli")
    assert (resolved.get("model"), resolved.source("model")) == ("env-model", "environment")

    stored = resolve_config(cli={}, env={}, workspace_root=workspace.root)
    assert (stored.get("model"), stored.source("model")) == ("stored-model", "workspace-config")

    default = resolve_config(cli={}, env={})
    assert (default.get("provider"), default.source("provider")) == ("deterministic", "default")
    (workspace.root / CONFIG_NAME).write_text(json.dumps({"nonsense": 1}), encoding="utf-8")
    with pytest.raises(WorkspaceError, match="unknown Workspace config settings"):
        resolve_config(cli={}, env={}, workspace_root=workspace.root)
    (workspace.root / CONFIG_NAME).write_text(
        json.dumps({"workspace": "/elsewhere"}), encoding="utf-8"
    )
    with pytest.raises(WorkspaceError, match="unknown Workspace config settings"):
        resolve_config(cli={}, env={}, workspace_root=workspace.root)


# --- CLI surface ------------------------------------------------------------


def _cv(*args: str, env: dict[str, str] | None = None) -> CliRun:
    return run_cli(*args, env=env)


def test_every_parser_command_has_a_registered_handler() -> None:
    """Registration is derived from the parser, not from a hand-kept list.

    `main()` dispatches through the handler registry, so a subcommand added to
    the parser without a handler would fail only when someone ran it. This
    reads the choices out of the parser itself, so forgetting to register one
    fails here instead.
    """
    from cv_engine.cli import _HANDLERS, build_parser

    subparsers = next(
        action
        for action in build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert set(subparsers.choices) == set(_HANDLERS)


def test_cli_module_entry_point_reports_the_failure_exit_code(tmp_path: Path) -> None:
    """The one guard the in-process runner cannot give: a real process.

    Every other CLI test here calls `main()` directly, which proves the exit
    code the function returns, not the status a shell sees. This runs the
    module entry point for real, so a broken `__main__` block or a swallowed
    exit code fails somewhere.
    """
    plain = tmp_path / "unmarked-process"
    plain.mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "cv_engine.cli", "--workspace", str(plain), "list"],
        text=True,
        capture_output=True,
        check=False,
        cwd=SOURCE_ROOT,
    )

    assert result.returncode == 2
    assert "no v2 Workspace marker" in result.stderr


@pytest.fixture
def legacy_root(tmp_path: Path) -> Path:
    """A v1 root as the guards see one: tracking data, no v2 marker.

    v1 is a frozen archive. The guards exist so no v2 command ever opens or
    writes into it, which is the only reason the archive stays trustworthy.
    """
    root = tmp_path / "legacy-source"
    (root / "jobs").mkdir(parents=True)
    (root / "jobs/status.csv").write_text("company,role\nalpha,dev\n", encoding="utf-8")
    (root / "base").mkdir()
    (root / "base/cv_base.md").write_text("# legacy base\n", encoding="utf-8")
    return root


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_cli_workspace_surface_guards_normal_and_unmarked_roots(
    tmp_path: Path, workspace_root: Path
) -> None:
    root = tmp_path / "cli-ws"
    created = _cv(
        "--workspace", str(root), "workspace", "init", "--purpose", "test", "--data-class", "test"
    )
    assert created.returncode == 0, created.stderr
    identity = json.loads(created.stdout)
    assert identity["purpose"] == "test"
    assert identity["data_class"] == "test"

    status = _cv("--workspace", str(root), "workspace", "status")
    assert status.returncode == 0, status.stderr
    reported = json.loads(status.stdout)
    assert reported["workspace_id"] == identity["workspace_id"]
    assert reported["installation_id"] == identity["installation_id"]
    assert reported["configuration"]["provider"]["source"] == "default"
    plain = tmp_path / "plain"
    plain.mkdir()
    result = _cv("--workspace", str(plain), "list")
    assert result.returncode == 2
    assert "no v2 Workspace marker" in result.stderr
    result = _cv("--repo", str(workspace_root), "workspace", "status")
    assert result.returncode == 0, result.stderr
    assert "--repo is deprecated" in result.stderr
    assert json.loads(result.stdout)["root"] == str(workspace_root)


def test_cli_commands_fail_closed_without_writes(tmp_path: Path, legacy_root: Path) -> None:
    plain = tmp_path / "plain-cli-root"
    plain.mkdir()

    unknown = create_workspace(tmp_path / "unknown-version")
    unknown_marker = unknown.root / MARKER_NAME
    unknown_payload = json.loads(unknown_marker.read_text(encoding="utf-8"))
    unknown_payload["workspace_version"] = 999
    unknown_marker.write_text(json.dumps(unknown_payload), encoding="utf-8")

    unsafe = create_workspace(tmp_path / "unsafe-live", purpose="live", data_class="live")
    unsafe_marker = unsafe.root / MARKER_NAME
    unsafe_payload = json.loads(unsafe_marker.read_text(encoding="utf-8"))
    unsafe_payload["purpose"] = "development"
    unsafe_marker.write_text(json.dumps(unsafe_payload), encoding="utf-8")

    roots = [
        (plain, "no v2 Workspace marker"),
        (legacy_root, "is a legacy v1 root"),
        (unknown.root, "unsupported Workspace version 999"),
        (unsafe.root, "may not open live data"),
    ]
    commands = [("list",)]
    for root, expected_error in roots:
        before = _tree(root)
        for command in commands:
            result = _cv("--workspace", str(root), *command)
            assert result.returncode == 2, result.stdout + result.stderr
            assert expected_error in result.stderr
            assert _tree(root) == before


def test_cli_exposes_no_migration_command(workspace_root: Path) -> None:
    """v1 is an archive, so the engine offers no way to migrate it in.

    Asserted at the CLI surface rather than by absence of a module, so a
    future re-added migration path has to be a deliberate decision.
    """
    for command in ("migrate", "inventory-legacy"):
        result = _cv("--workspace", str(workspace_root), command)
        assert result.returncode == 2
        assert "invalid choice" in result.stderr


def test_marker_is_validated_before_workspace_config_is_read(tmp_path: Path) -> None:
    plain = tmp_path / "unmarked"
    plain.mkdir()
    (plain / CONFIG_NAME).write_text("{invalid json", encoding="utf-8")

    result = _cv("--workspace", str(plain), "list")

    assert result.returncode == 2
    assert "no v2 Workspace marker" in result.stderr
    assert "unreadable Workspace config" not in result.stderr


@pytest.mark.parametrize("child", ["data", "artifacts", "tmp", "logs"])
def test_symlinked_default_child_roots_are_refused(tmp_path: Path, child: str) -> None:
    workspace = create_workspace(tmp_path / f"workspace-{child}")
    child_path = workspace.root / child
    child_path.rmdir()
    outside = tmp_path / f"outside-{child}"
    outside.mkdir()
    child_path.symlink_to(outside, target_is_directory=True)

    with pytest.raises(WorkspaceError, match="Workspace root .* may not be a symlink"):
        load_workspace(workspace.root)


@pytest.mark.parametrize("source", ["flag", "environment"])
def test_database_override_is_contained_inside_state_root(tmp_path: Path, source: str) -> None:
    workspace = create_workspace(tmp_path / f"database-{source}", purpose="test", data_class="test")

    def run(value: Path | str) -> CliRun:
        if source == "flag":
            return _cv("--workspace", str(workspace.root), "--db", str(value), "init")
        return _cv(
            "--workspace",
            str(workspace.root),
            "init",
            env={"CV_DATABASE": str(value)},
        )

    relative = run("relative.sqlite3")
    assert relative.returncode == 0, relative.stderr
    assert (workspace.state_root / "relative.sqlite3").is_file()

    absolute_path = workspace.state_root / "absolute.sqlite3"
    absolute = run(absolute_path)
    assert absolute.returncode == 0, absolute.stderr
    assert absolute_path.is_file()

    outside_path = tmp_path / f"outside-{source}.sqlite3"
    outside = run(outside_path)
    assert outside.returncode == 2
    assert "escapes configured root" in outside.stderr
    assert not outside_path.exists()

    outside_directory = tmp_path / f"symlink-outside-{source}"
    outside_directory.mkdir()
    link = workspace.state_root / "escape"
    link.symlink_to(outside_directory, target_is_directory=True)
    escaped = run("escape/escaped.sqlite3")
    assert escaped.returncode == 2
    assert "escapes configured root" in escaped.stderr
    assert not (outside_directory / "escaped.sqlite3").exists()


# --- backup and restore -----------------------------------------------------


def _seeded_workspace(root: Path):
    """A Workspace with something in every root a backup is supposed to carry."""
    workspace = create_workspace(root, purpose="test", data_class="test")
    initialize(workspace.database_path)
    for name in ("base", "profiles", "rendering", "config", "ai"):
        directory = workspace.knowledge_root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
    (workspace.artifacts_root / "app-1").mkdir(parents=True, exist_ok=True)
    (workspace.artifacts_root / "app-1/resume.md").write_text("# resume\n", encoding="utf-8")
    (workspace.temp_root / "scratch.txt").write_text("discard me\n", encoding="utf-8")
    (workspace.logs_root / "run.log").write_text("discard me\n", encoding="utf-8")
    return workspace


def test_backup_restores_into_a_new_workspace_that_opens(tmp_path: Path) -> None:
    workspace = _seeded_workspace(tmp_path / "ws")
    report = backup_workspace(workspace, tmp_path / "backup")

    assert report.database.is_file()
    assert "artifacts" in report.directories
    assert "base" in report.directories
    # Scratch and diagnostics are not state; carrying them would make every
    # backup bigger and none of them more restorable.
    assert not (report.root / "tmp").exists()
    assert not (report.root / "logs").exists()

    restored = restore_workspace(report.root, tmp_path / "restored")
    assert restored.workspace_id == workspace.workspace_id
    assert current_schema_version(restored.database_path) == current_schema_version(
        workspace.database_path
    )
    assert (restored.artifacts_root / "app-1/resume.md").read_text(encoding="utf-8") == "# resume\n"


def test_backup_and_restore_refuse_to_overlay_existing_directories(tmp_path: Path) -> None:
    workspace = _seeded_workspace(tmp_path / "ws")

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep.txt").write_text("keep\n", encoding="utf-8")
    with pytest.raises(BackupError, match="non-empty directory"):
        backup_workspace(workspace, occupied)
    assert (occupied / "keep.txt").exists()

    # A backup inside its own Workspace would be captured by the next backup and
    # would grow without bound.
    with pytest.raises(BackupError, match="inside its own Workspace"):
        backup_workspace(workspace, workspace.root / "self-backup")

    report = backup_workspace(workspace, tmp_path / "backup")
    with pytest.raises(BackupError, match="non-empty directory"):
        restore_workspace(report.root, occupied)
    assert (occupied / "keep.txt").exists()

    with pytest.raises(BackupError, match="no .cv-workspace.json"):
        restore_workspace(tmp_path / "not-a-backup", tmp_path / "elsewhere")


def test_backup_captures_committed_writes_still_in_the_write_ahead_log(tmp_path: Path) -> None:
    """The reason the backup goes through SQLite rather than copying the file."""
    workspace = _seeded_workspace(tmp_path / "ws")
    connection = connect(workspace.database_path)
    connection.execute(
        "INSERT INTO applications(id, company, target_role, current_status, notes, "
        "source, created_at, updated_at) VALUES(?, ?, ?, ?, '', 'manual', ?, ?)",
        ("app-wal", "alpha", "dev", "saved", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )
    connection.commit()

    report = backup_workspace(workspace, tmp_path / "backup")
    connection.close()

    restored = restore_workspace(report.root, tmp_path / "restored")
    with connect(restored.database_path) as check:
        rows = check.execute("SELECT id FROM applications").fetchall()
    assert [row["id"] for row in rows] == ["app-wal"]


def test_knowledge_source_provenance_is_recorded_and_incomplete_sources_are_refused(
    tmp_path: Path, workspace_root: Path
) -> None:
    seeded = create_workspace(tmp_path / "seeded", knowledge_source=workspace_root)
    marker = json.loads((seeded.root / MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["knowledge_source"] == str(workspace_root)
    assert len(marker["knowledge_source_hash"]) == 64

    # Same bytes seeded twice hash the same; a changed source does not.
    again = create_workspace(tmp_path / "again", knowledge_source=workspace_root)
    again_marker = json.loads((again.root / MARKER_NAME).read_text(encoding="utf-8"))
    assert again_marker["knowledge_source_hash"] == marker["knowledge_source_hash"]
    (workspace_root / "base/extra.md").write_text("# extra\n", encoding="utf-8")
    changed = create_workspace(tmp_path / "changed", knowledge_source=workspace_root)
    changed_marker = json.loads((changed.root / MARKER_NAME).read_text(encoding="utf-8"))
    assert changed_marker["knowledge_source_hash"] != marker["knowledge_source_hash"]

    partial = tmp_path / "partial"
    (partial / "base").mkdir(parents=True)
    with pytest.raises(WorkspaceError, match="knowledge source is incomplete"):
        create_workspace(tmp_path / "from-partial", knowledge_source=partial)
    assert not (tmp_path / "from-partial" / MARKER_NAME).exists()

    plain = create_workspace(tmp_path / "plain")
    plain_marker = json.loads((plain.root / MARKER_NAME).read_text(encoding="utf-8"))
    assert plain_marker["knowledge_source"] is None
    assert plain_marker["knowledge_source_hash"] is None
