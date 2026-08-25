"""Workspace lifecycle commands: init, status, and database upgrade."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..infrastructure.persistence import (
    Repository,
    create_database_engine,
    current_database_revision,
    upgrade_database,
)
from ..runtime.config import mask_value
from ..runtime.workspace import Workspace, create_workspace, load_workspace
from .context import CommandContext, _command, _workspace_config
from .output import _print


def _database_status(database_url: str) -> tuple[str | None, list[str]]:
    engine = create_database_engine(database_url)
    try:
        return current_database_revision(engine), Repository(engine).integrity_check()
    finally:
        engine.dispose()


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
        database_url = str(config.get("database_url"))
        schema_version, _ = _database_status(database_url)
        _print(
            {
                **opened.describe(),
                "installation_id": opened.installation_id(),
                "database_url": mask_value("database_url", database_url),
                "schema_version": schema_version,
                "configuration": config.describe(),
            }
        )
        return 0
    if args.workspace_command == "upgrade":
        opened = opened or load_workspace(root)
        database_url = str(config.get("database_url"))
        before, after = upgrade_database(database_url)
        _, integrity_problems = _database_status(database_url)
        if integrity_problems:
            raise ValueError(
                "workspace upgrade completed but the database integrity check failed: "
                + "; ".join(integrity_problems)
            )
        _print(
            {
                **opened.describe(),
                "database_url": mask_value("database_url", database_url),
                "schema_version_before": before,
                "schema_version": after,
                "upgraded": before != after,
            }
        )
        return 0
    raise ValueError(f"unknown workspace command: {args.workspace_command}")


@_command("workspace", needs="root")
def _workspace(context: CommandContext) -> int:
    args = context.args
    if args.workspace_command == "init":
        return workspace_command(context.root, context.config, args)
    workspace = load_workspace(context.root)
    return workspace_command(
        context.root, _workspace_config(args, workspace), args, opened=workspace
    )
