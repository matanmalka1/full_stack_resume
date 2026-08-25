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

from cv_engine.runtime.composition import build_services
from cv_engine.runtime.config import CONFIG_NAME, parse_env_file, resolve_config
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


def test_env_file_sits_below_the_real_environment_and_secrets_are_masked(tmp_path: Path) -> None:
    """A `.env` supplies values, an exported variable still overrides it.

    The precedence direction is the point. A stale `.env` silently beating a
    variable the developer exported in this shell is what turns a config
    mistake into a defect that reads as a code bug.
    """
    workspace = create_workspace(tmp_path / "ws")
    (workspace.root / ".env").write_text(
        "# comment\n"
        "export CV_DATABASE_URL='postgresql+psycopg://cv:filepw@127.0.0.1:5433/fromfile'\n"
        'CV_MODEL="model-from-file"\n'
        "OPENAI_API_KEY=sk-from-file\n",
        encoding="utf-8",
    )

    resolved = resolve_config(cli={}, env={}, workspace_root=workspace.root)
    assert resolved.source("model") == "env-file"
    assert resolved.get("model") == "model-from-file"
    # The value the code connects with is the real one, never the masked form.
    assert resolved.get("database_url").endswith("/fromfile")
    assert resolved.get("openai_api_key") == "sk-from-file"

    overridden = resolve_config(
        cli={}, env={"CV_MODEL": "env-model"}, workspace_root=workspace.root
    )
    assert (overridden.get("model"), overridden.source("model")) == ("env-model", "environment")

    # Masking happens only at the display boundary, and only for secrets.
    described = resolved.describe()
    assert described["database_url"]["value"] == "***"
    assert described["openai_api_key"]["value"] == "***"
    assert described["model"]["value"] == "model-from-file"
    # Sources stay visible: "why is this value in effect" must remain answerable.
    assert described["database_url"]["source"] == "env-file"
    # An unset secret reports as unset rather than as a withheld value.
    assert resolve_config(cli={}, env={}).describe()["openai_api_key"]["value"] is None


def test_env_file_parsing_ignores_comments_blanks_and_malformed_lines() -> None:
    assert parse_env_file(
        "\n# comment\nexport A=1\nB='two'\nC=\nnot-an-assignment\n  D = spaced \n"
    ) == {"A": "1", "B": "two", "C": "", "D": "spaced"}


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
    assert reported["schema_version"] == "0002"
    assert reported["database_url"] == reported["configuration"]["database_url"]["value"]
    assert reported["configuration"]["provider"]["source"] == "default"
    upgraded = _cv("--workspace", str(root), "workspace", "upgrade")
    assert upgraded.returncode == 0, upgraded.stderr
    assert json.loads(upgraded.stdout)["upgraded"] is False
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


def test_cli_exposes_no_retired_storage_commands(workspace_root: Path) -> None:
    """v1 is an archive, so the engine offers no way to migrate it in.

    Asserted at the CLI surface rather than by absence of a module, so a
    future re-added migration path has to be a deliberate decision.
    """
    for command in ("migrate", "inventory-legacy", "init"):
        result = _cv("--workspace", str(workspace_root), command)
        assert result.returncode == 2
        assert "invalid choice" in result.stderr
    for command in ("backup", "restore"):
        result = _cv("--workspace", str(workspace_root), "workspace", command)
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


def test_symlinked_default_child_roots_are_refused(tmp_path: Path) -> None:
    for child in ("data", "artifacts", "tmp", "logs"):
        workspace = create_workspace(tmp_path / f"workspace-{child}")
        child_path = workspace.root / child
        child_path.rmdir()
        outside = tmp_path / f"outside-{child}"
        outside.mkdir()
        child_path.symlink_to(outside, target_is_directory=True)

        with pytest.raises(WorkspaceError, match="Workspace root .* may not be a symlink"):
            load_workspace(workspace.root)


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
