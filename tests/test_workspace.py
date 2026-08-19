"""Workspace identity, fail-closed guards, config precedence, and legacy reads.

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

from cv_engine.infrastructure.legacy_source import LegacySourceError, LegacyV1Source
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

    with pytest.raises(WorkspaceError, match="read-only migration source adapter"):
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


# --- read-only legacy source adapter ---------------------------------------


@pytest.fixture
def legacy_source_root(tmp_path: Path) -> Path:
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


def test_inventory_reads_a_legacy_root_without_writing_to_it(legacy_source_root: Path) -> None:
    before = _tree(legacy_source_root)
    source = LegacyV1Source(legacy_source_root)
    with pytest.raises(LegacySourceError, match="take an inventory"):
        source.read_text("jobs/status.csv")
    inventory = source.inventory()

    assert set(inventory.files) == {"jobs/status.csv", "base/cv_base.md"}
    assert inventory.inventory_hash
    assert _tree(legacy_source_root) == before
    assert not (legacy_source_root / MARKER_NAME).exists()
    assert source.inventory().inventory_hash == inventory.inventory_hash
    assert source.read_text("base/cv_base.md") == "# legacy base\n"
    (legacy_source_root / "base/cv_base.md").write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(LegacySourceError, match="changed during the run"):
        source.read_text("base/cv_base.md")
    with pytest.raises(LegacySourceError, match="base/cv_base.md"):
        source.verify_unchanged()


def test_legacy_reads_refuse_traversal_unknown_files_and_v2_workspaces(
    legacy_source_root: Path, tmp_path: Path
) -> None:
    source = LegacyV1Source(legacy_source_root)
    source.inventory()
    with pytest.raises(LegacySourceError, match="escapes the legacy source"):
        source.read_bytes("../secrets.txt")
    with pytest.raises(LegacySourceError, match="source-relative"):
        source.read_bytes(legacy_source_root / "jobs/status.csv")
    with pytest.raises(LegacySourceError, match="not part of the bound inventory"):
        source.read_bytes("jobs/missing.csv")
    workspace = create_workspace(tmp_path / "ws")
    with pytest.raises(LegacySourceError, match="v2 Workspace marker"):
        LegacyV1Source(workspace.root)


def test_legacy_database_connection_cannot_write(tmp_path: Path) -> None:
    import sqlite3

    root = tmp_path / "legacy-db"
    (root / "data").mkdir(parents=True)
    database = root / "data/applications.sqlite3"
    with sqlite3.connect(database) as seed:
        seed.execute("CREATE TABLE applications(id TEXT PRIMARY KEY)")
        seed.execute("INSERT INTO applications VALUES('alpha')")
        seed.commit()

    source = LegacyV1Source(root)
    source.inventory()
    connection = source.open_database("data/applications.sqlite3")
    assert [row["id"] for row in connection.execute("SELECT id FROM applications")] == ["alpha"]
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("INSERT INTO applications VALUES('beta')")
    connection.close()


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


def test_cli_workspace_surface_guards_normal_and_legacy_roots(
    tmp_path: Path, legacy_source_root: Path, v1_repo: Path
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
    result = _cv("workspace", "inventory-legacy", "--source", str(legacy_source_root))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["file_count"] == 2
    assert report["marker_written"] is False
    assert not (legacy_source_root / MARKER_NAME).exists()
    result = _cv("--repo", str(v1_repo), "workspace", "status")
    assert result.returncode == 0, result.stderr
    assert "--repo is deprecated" in result.stderr
    assert json.loads(result.stdout)["root"] == str(v1_repo)


def test_cli_normal_and_historical_verification_commands_fail_closed_without_writes(
    tmp_path: Path, legacy_source_root: Path
) -> None:
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
        (legacy_source_root, "read-only migration source adapter"),
        (unknown.root, "unsupported Workspace version 999"),
        (unsafe.root, "may not open live data"),
    ]
    commands = [
        ("list",),
        ("migrate", "verify-source"),
        ("migrate", "verify-live"),
    ]
    for root, expected_error in roots:
        before = _tree(root)
        for command in commands:
            result = _cv("--workspace", str(root), *command)
            assert result.returncode == 2, result.stdout + result.stderr
            assert expected_error in result.stderr
            assert _tree(root) == before


def test_cli_retired_in_place_migration_commands_are_not_exposed(v1_repo: Path) -> None:
    for command in ("inventory", "snapshot", "test", "dry-run", "apply", "reconcile"):
        result = _cv("--workspace", str(v1_repo), "migrate", command)
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
