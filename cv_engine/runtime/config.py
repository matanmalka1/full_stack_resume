from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workspace import WorkspaceError

CONFIG_NAME = "cv-workspace.config.json"


@dataclass(frozen=True)
class Setting:
    """One configurable value and where it may come from.

    `workspace_scoped` is false only for settings that select the Workspace
    itself: a value stored inside a Workspace cannot decide which Workspace to
    open without arguing with itself.
    """

    name: str
    env: str
    default: Any = None
    workspace_scoped: bool = True


# The HTTP body limit lives here rather than in the API package because the
# test plan (§10) requires the chosen value to be recorded in the config
# contract, and because `cv workspace status` is then able to report it.
# 2 MiB sits inside the approved 1-2 MB order of magnitude.
API_MAX_BODY_BYTES_DEFAULT = 2 * 1024 * 1024

SETTINGS: dict[str, Setting] = {
    setting.name: setting
    for setting in (
        Setting("workspace", "CV_WORKSPACE", workspace_scoped=False),
        Setting("database", "CV_DATABASE"),
        Setting("provider", "CV_PROVIDER", default="deterministic"),
        Setting("model", "CV_MODEL", default="gpt-5.6"),
        Setting("api_max_body_bytes", "CV_API_MAX_BODY_BYTES", default=API_MAX_BODY_BYTES_DEFAULT),
        # Unset in production: the built UI is served same-origin, so there is no
        # second origin to allow. A value here is the one development Vite origin
        # and nothing else — never a wildcard, never a list.
        Setting("api_dev_origin", "CV_API_DEV_ORIGIN", default=None),
    )
}

SOURCES = ("cli", "environment", "workspace-config", "default")


@dataclass(frozen=True)
class Resolved:
    value: Any
    source: str


class RuntimeConfig:
    """Resolved settings plus the layer each one came from.

    The source is kept because `cv workspace status` has to be able to answer
    "why is this value in effect", and because a setting silently arriving from
    an unexpected layer is the kind of thing that only shows up as a wrong
    artifact much later.
    """

    def __init__(self, values: dict[str, Resolved]):
        self.values = values

    def get(self, name: str) -> Any:
        return self.values[name].value

    def source(self, name: str) -> str:
        return self.values[name].source

    def describe(self) -> dict[str, dict[str, Any]]:
        return {
            name: {"value": resolved.value, "source": resolved.source}
            for name, resolved in sorted(self.values.items())
        }


def load_workspace_config(root: Path) -> dict[str, Any]:
    path = Path(root) / CONFIG_NAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"unreadable Workspace config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkspaceError(f"Workspace config must be an object: {path}")
    unknown = sorted(
        set(payload) - {name for name, setting in SETTINGS.items() if setting.workspace_scoped}
    )
    if unknown:
        raise WorkspaceError(f"unknown Workspace config settings in {path}: {', '.join(unknown)}")
    return payload


def resolve_config(
    *,
    cli: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    workspace_root: Path | None = None,
) -> RuntimeConfig:
    """Apply the precedence CLI > environment > Workspace config > default."""
    cli = cli or {}
    env = env if env is not None else {}
    stored = load_workspace_config(workspace_root) if workspace_root is not None else {}
    values: dict[str, Resolved] = {}
    for name, setting in SETTINGS.items():
        if cli.get(name) is not None:
            values[name] = Resolved(cli[name], "cli")
        elif env.get(setting.env):
            values[name] = Resolved(env[setting.env], "environment")
        elif setting.workspace_scoped and stored.get(name) is not None:
            values[name] = Resolved(stored[name], "workspace-config")
        else:
            values[name] = Resolved(setting.default, "default")
    return RuntimeConfig(values)
