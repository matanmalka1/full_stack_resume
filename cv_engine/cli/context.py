"""Resolving the fixed application root and building command services.

`CommandContext` carries what one command was given; the `_command` registry
binds a command name to its handler.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..application.ports import ApplicationRepository
from ..runtime.composition import Services, build_services
from ..runtime.config import resolve_config
from ..runtime.paths import AppPaths


def _repo_root() -> Path:
    # cli.py used to sit directly in cv_engine/, so two .parent calls reached
    # the repo root. This module sits one level deeper, in cv_engine/cli/, so
    # it needs a third .parent to land on the same directory as before.
    test_root = os.environ.get("CV_TEST_PROJECT_ROOT")
    return Path(test_root).resolve() if test_root else Path(__file__).resolve().parent.parent.parent


def _resolve_root() -> tuple[Path, Any]:
    """Return the fixed repository root and its configuration.

    The root is not a command's to choose: it comes from the installed
    location, or from `CV_TEST_PROJECT_ROOT` for an isolated test project.
    """
    root = _repo_root().resolve()
    config = resolve_config(env=os.environ, project_root=root)
    return root, config


@dataclass
class CommandContext:
    """What one command was given.

    Every command uses the same fixed root and composition.
    """

    args: argparse.Namespace
    root: Path
    config: Any
    paths: AppPaths | None = None
    services: Services | None = None

    @property
    def opened_paths(self) -> AppPaths:
        assert self.paths is not None
        return self.paths

    @property
    def built_services(self) -> Services:
        assert self.services is not None
        return self.services

    @property
    def repository(self) -> ApplicationRepository:
        return self.built_services.repository


Handler = Callable[[CommandContext], int]


_HANDLERS: dict[str, Handler] = {}


def _command(name: str) -> Callable[[Handler], Handler]:
    """Register the handler for one top-level command."""

    def register(handler: Handler) -> Handler:
        _HANDLERS[name] = handler
        return handler

    return register


def _build_context(args: argparse.Namespace, root: Path, config: Any) -> CommandContext:
    context = CommandContext(args=args, root=root, config=config)
    context.paths = AppPaths.from_root(root)
    context.services = build_services(context.paths, config=context.config)
    return context
