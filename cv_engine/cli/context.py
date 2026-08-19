"""Resolving the selected Workspace root and building the stage a command needs.

`CommandContext` carries what one command was given, opened as far as that
command needs; the `_command` registry binds a command name to its handler
and the stage (`root`, `database`, or `services`) it requires.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..application.ports import ApplicationRepository
from ..infrastructure.paths import resolve_within
from ..runtime.composition import Services, build_services
from ..runtime.config import resolve_config
from ..runtime.workspace import Workspace, load_workspace


def _repo_root() -> Path:
    # cli.py used to sit directly in cv_engine/, so two .parent calls reached
    # the repo root. This module sits one level deeper, in cv_engine/cli/, so
    # it needs a third .parent to land on the same directory as before.
    return Path(__file__).resolve().parent.parent.parent


def _resolve_root(args: argparse.Namespace) -> tuple[Path, Any]:
    """The selected root plus the resolved configuration behind it.

    `--repo` stays accepted because v1 scripts pass it, but it is an alias with
    a warning rather than a second concept: one Workspace selection, resolved
    through CLI > environment > Workspace config > default.
    """
    if args.repo is not None:
        print("WARNING: --repo is deprecated; use --workspace", file=sys.stderr)
    selected = args.workspace or args.repo
    config = resolve_config(cli={"workspace": selected, "database": args.db}, env=os.environ)
    root = Path(config.get("workspace") or _repo_root()).resolve()
    return root, config


@dataclass
class CommandContext:
    """What one command was given, opened as far as that command needs.

    A command's stage is what it may touch: `workspace init` runs before a
    Workspace exists, `init` creates the schema the services would otherwise
    expect, and every other command gets built services. Building only up to
    the stage keeps each command's fail-closed order the same as before the
    split.
    """

    args: argparse.Namespace
    root: Path
    config: Any
    workspace: Workspace | None = None
    database_path: Path | None = None
    services: Services | None = None

    @property
    def opened_workspace(self) -> Workspace:
        assert self.workspace is not None
        return self.workspace

    @property
    def built_services(self) -> Services:
        assert self.services is not None
        return self.services

    @property
    def repository(self) -> ApplicationRepository:
        return self.built_services.repository

    @property
    def opened_database_path(self) -> Path:
        assert self.database_path is not None
        return self.database_path


Handler = Callable[[CommandContext], int]


_HANDLERS: dict[str, tuple[str, Handler]] = {}


def _command(name: str, *, needs: str = "services") -> Callable[[Handler], Handler]:
    """Register the handler for one top-level command and the stage it needs."""

    def register(handler: Handler) -> Handler:
        _HANDLERS[name] = (needs, handler)
        return handler

    return register


def _workspace_config(args: argparse.Namespace, workspace: Workspace) -> Any:
    return resolve_config(
        cli={"workspace": args.workspace or args.repo, "database": args.db},
        env=os.environ,
        workspace_root=workspace.root,
    )


def _build_context(args: argparse.Namespace, root: Path, config: Any, needs: str) -> CommandContext:
    context = CommandContext(args=args, root=root, config=config)
    if needs == "root":
        return context
    # Every remaining command is a normal v2 command, so it opens the
    # Workspace fail-closed before it touches state.
    context.workspace = load_workspace(root)
    context.config = _workspace_config(args, context.workspace)
    db_override = context.config.get("database")
    context.database_path = (
        resolve_within(context.workspace.state_root, db_override)
        if db_override
        else context.workspace.database_path
    )
    if needs == "database":
        return context
    context.services = build_services(context.workspace, database_path=context.database_path)
    return context
