"""Workspace lifecycle commands: init, status, backup, restore, schema init."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..infrastructure.paths import resolve_within
from ..infrastructure.persistence import (
    Repository,
    SchemaError,
    apply_migrations,
    current_schema_version,
    initialize,
)
from ..runtime.backup import backup_workspace, restore_workspace
from ..runtime.workspace import Workspace, create_workspace, load_workspace
from .context import CommandContext, _command, _workspace_config
from .output import _print


def _effective_database_path(opened: Workspace, config: Any) -> Path:
    configured_database = config.get("database")
    return (
        resolve_within(opened.state_root, configured_database)
        if configured_database
        else opened.database_path
    )


def workspace_command(
    root: Path,
    config: Any,
    args: argparse.Namespace,
    *,
    opened: Workspace | None = None,
) -> int:
    if args.workspace_command == "init":
        created = create_workspace(
            root,
            purpose=args.purpose,
            data_class=args.data_class,
            knowledge_source=args.knowledge_from.resolve() if args.knowledge_from else None,
        )
        _print(
            {**created.describe(), "installation_id": created.installation_id(), "created": True}
        )
        return 0
    if args.workspace_command == "status":
        opened = opened or load_workspace(root)
        database_path = _effective_database_path(opened, config)
        _print(
            {
                **opened.describe(),
                "installation_id": opened.installation_id(),
                "database": str(database_path),
                "schema_version": current_schema_version(database_path),
                "configuration": config.describe(),
            }
        )
        return 0
    if args.workspace_command == "backup":
        opened = opened or load_workspace(root)
        database_path = _effective_database_path(opened, config)
        _print(
            backup_workspace(
                opened, args.into.resolve(), database_path=database_path
            ).describe()
        )
        return 0
    if args.workspace_command == "upgrade":
        opened = opened or load_workspace(root)
        database_path = _effective_database_path(opened, config)
        before = current_schema_version(database_path)
        after = apply_migrations(database_path)
        integrity_problems = Repository(database_path).integrity_check()
        if integrity_problems:
            raise SchemaError(
                "workspace upgrade completed but the database integrity check failed: "
                + "; ".join(integrity_problems)
            )
        _print(
            {
                **opened.describe(),
                "database": str(database_path),
                "schema_version_before": before,
                "schema_version": after,
                "upgraded": before != after,
            }
        )
        return 0
    if args.workspace_command == "restore":
        # Restore runs before the restored Workspace exists, so it opens the
        # backup rather than the selected root. Reporting the schema version
        # proves the archive is an openable database and not just files.
        restored = restore_workspace(args.backup_from.resolve(), args.into.resolve())
        _print(
            {
                **restored.describe(),
                "restored_from": str(args.backup_from.resolve()),
                "schema_version": current_schema_version(restored.database_path),
            }
        )
        return 0
    raise ValueError(f"unknown workspace command: {args.workspace_command}")


@_command("workspace", needs="root")
def _workspace(context: CommandContext) -> int:
    args = context.args
    if args.workspace_command not in {"status", "backup", "upgrade"}:
        return workspace_command(context.root, context.config, args)
    workspace = load_workspace(context.root)
    return workspace_command(
        context.root, _workspace_config(args, workspace), args, opened=workspace
    )


@_command("init", needs="database")
def _init(context: CommandContext) -> int:
    database_path = context.opened_database_path
    initialize(database_path)
    _print({"database": str(database_path), "schema_initialized": True})
    return 0
