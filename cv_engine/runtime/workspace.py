from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

from ..domain.models import StrictModel
from ..infrastructure.paths import relative_within, resolve_within
from ..util import new_id, sha256_file, sha256_text, utc_now

MARKER_NAME = ".cv-workspace.json"
WORKSPACE_VERSION = 2
KNOWLEDGE_DIRS = ("base", "profiles", "rendering", "config", "ai")

Purpose = Literal["development", "test", "live"]
DataClass = Literal["copy", "test", "live"]

# Live data is only ever opened by a runtime that declares itself live. This is
# the guard that stops a development or test process from touching the real
# Workspace, and it is expressed in marker metadata rather than path naming.
UNSAFE_COMBINATIONS = {("development", "live"), ("test", "live")}

ROOT_NAMES = ("knowledge_root", "state_root", "artifacts_root", "temp_root", "logs_root")


class WorkspaceError(RuntimeError):
    """The selected directory is not a Workspace this process may open."""


class WorkspaceMarker(StrictModel):
    workspace_id: str
    workspace_version: int
    purpose: Purpose
    data_class: DataClass
    created_at: str
    roots: dict[str, str] = {}
    # Where `--knowledge-from` copied the seed knowledge, and what it hashed to
    # at the time. Recorded rather than enforced: the copy happens once, into a
    # fresh Workspace, over knowledge that can be regenerated, so the cost of a
    # wrong source is one `workspace init`. What is expensive is not being able
    # to tell later which source a Workspace was seeded from.
    knowledge_source: str | None = None
    knowledge_source_hash: str | None = None


def default_roots(root: Path) -> dict[str, Path]:
    return {
        "knowledge_root": root,
        "state_root": root / "data",
        "artifacts_root": root / "artifacts",
        "temp_root": root / "tmp",
        "logs_root": root / "logs",
    }


class Workspace:
    """One candidate Workspace: its identity, its guards, and its five roots.

    Nothing else in the engine builds a path from a repository root. Services
    receive a Workspace, so relocating state or artifacts is a marker change
    rather than a code change, and a directory that carries no v2 marker cannot
    be opened by accident.
    """

    def __init__(self, root: Path, marker: WorkspaceMarker):
        resolved_root = Path(root).resolve()
        self.root = resolve_within(resolved_root, resolved_root)
        self.marker = marker
        resolved: dict[str, Path] = {}
        for name, candidate in default_roots(self.root).items():
            if name != "knowledge_root" and candidate.is_symlink():
                raise WorkspaceError(f"Workspace root {name} may not be a symlink: {candidate}")
            try:
                resolved[name] = resolve_within(self.root, candidate)
            except ValueError as exc:
                raise WorkspaceError(
                    f"Workspace root {name} escapes the Workspace: {candidate}"
                ) from exc
        for name, value in marker.roots.items():
            if name not in ROOT_NAMES:
                raise WorkspaceError(f"unknown Workspace root: {name}")
            try:
                candidate = resolve_within(self.root, value)
            except ValueError as exc:
                raise WorkspaceError(
                    f"Workspace root {name} escapes the Workspace: {value}"
                ) from exc
            resolved[name] = candidate
        self.knowledge_root = resolved["knowledge_root"]
        self.state_root = resolved["state_root"]
        self.artifacts_root = resolved["artifacts_root"]
        self.temp_root = resolved["temp_root"]
        self.logs_root = resolved["logs_root"]

    @property
    def workspace_id(self) -> str:
        return self.marker.workspace_id

    @property
    def purpose(self) -> str:
        return self.marker.purpose

    @property
    def data_class(self) -> str:
        return self.marker.data_class

    def relative(self, path: Path) -> str:
        """A Workspace-relative POSIX path, or a refusal.

        Artifact rows store Workspace-relative paths so relocating a Workspace
        does not rewrite stored records or persist absolute local paths.
        """
        if not Path(path).is_absolute():
            raise WorkspaceError(f"path is outside the Workspace: {path}")
        try:
            return relative_within(self.root, path).as_posix()
        except ValueError as exc:
            raise WorkspaceError(f"path is outside the Workspace: {path}") from exc

    def installation_id(self) -> str:
        """Durable identity of this installation, distinct from the Workspace.

        Idempotency keys and audit records are scoped by installation, so the
        value must survive restarts and must not change when the same
        installation opens a different Workspace.
        """
        path = self.state_root / "installation.json"
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return str(payload["installation_id"])
            except (json.JSONDecodeError, KeyError) as exc:
                raise WorkspaceError(f"installation record is unreadable: {path}") from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        value = new_id()
        _write_json(path, {"installation_id": value, "created_at": utc_now()})
        return value

    def describe(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "workspace_version": self.marker.workspace_version,
            "purpose": self.purpose,
            "data_class": self.data_class,
            "created_at": self.marker.created_at,
            "root": str(self.root),
            "roots": {name: str(getattr(self, name)) for name in ROOT_NAMES},
        }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _check_combination(purpose: str, data_class: str) -> None:
    if (purpose, data_class) in UNSAFE_COMBINATIONS:
        raise WorkspaceError(
            f"a {purpose} process may not open {data_class} data; "
            "run live data only from a Workspace marked purpose=live"
        )


def create_workspace(
    root: Path,
    *,
    purpose: Purpose = "development",
    data_class: DataClass = "copy",
    roots: dict[str, str] | None = None,
    knowledge_source: Path | None = None,
) -> Workspace:
    """Create an isolated Workspace and its marker.

    A directory that already carries a marker is refused outright: creating a
    Workspace never rewrites an existing one. There is no override.
    """
    root = Path(root).resolve()
    _check_combination(purpose, data_class)
    if (root / MARKER_NAME).exists():
        raise WorkspaceError(f"a Workspace marker already exists at {root}")
    root.mkdir(parents=True, exist_ok=True)
    source = Path(knowledge_source).resolve() if knowledge_source is not None else None
    if source is not None:
        # Checked before the marker is built, not inside the copy: hashing an
        # incomplete source would record a hash for knowledge that was never
        # there, and an empty directory hashes just as happily as a full one.
        _require_complete_knowledge(source)
    marker = WorkspaceMarker(
        workspace_id=new_id(),
        workspace_version=WORKSPACE_VERSION,
        purpose=purpose,
        data_class=data_class,
        created_at=utc_now(),
        roots=roots or {},
        knowledge_source=str(source) if source else None,
        knowledge_source_hash=knowledge_source_hash(source) if source else None,
    )
    workspace = Workspace(root, marker)
    if source is not None:
        _copy_knowledge(source, workspace.knowledge_root)
    for directory in (
        workspace.knowledge_root,
        workspace.state_root,
        workspace.artifacts_root,
        workspace.temp_root,
        workspace.logs_root,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    _write_json(root / MARKER_NAME, marker.model_dump(mode="json"))
    return workspace


def _require_complete_knowledge(source: Path) -> None:
    missing = [name for name in KNOWLEDGE_DIRS if not (source / name).is_dir()]
    if missing:
        raise WorkspaceError(f"knowledge source is incomplete: missing {', '.join(missing)}")


def _copy_knowledge(source: Path, knowledge_root: Path) -> None:
    if source == knowledge_root:
        return
    _require_complete_knowledge(source)
    knowledge_root.mkdir(parents=True, exist_ok=True)
    for name in KNOWLEDGE_DIRS:
        target = knowledge_root / name
        if target.exists():
            raise WorkspaceError(f"refusing to overwrite existing knowledge directory: {target}")
        shutil.copytree(source / name, target)


def knowledge_source_hash(source: Path) -> str:
    """Hash the seed knowledge as copied: relative path and content, in order.

    Paths are part of the hash because two sources holding the same bytes under
    different names are different seeds, and a hash that could not tell them
    apart would be recording less than the directory listing already does.
    """
    digest = []
    for name in KNOWLEDGE_DIRS:
        directory = source / name
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            digest.append(f"{path.relative_to(source).as_posix()}:{sha256_file(path)}")
    return sha256_text("\n".join(digest))


def load_workspace(root: Path) -> Workspace:
    """Open a Workspace, or refuse.

    Fail-closed: a missing, unknown, or unsafe marker is an error rather
    than a default. Every normal v2 command reaches its data through this
    function, so there is one place where that decision is made.
    """
    root = Path(root).resolve()
    path = root / MARKER_NAME
    if not path.is_file():
        raise WorkspaceError(
            f"no v2 Workspace marker at {root}. Create one with 'cv workspace init'."
        )
    try:
        marker = WorkspaceMarker.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError) as exc:
        raise WorkspaceError(f"unreadable Workspace marker {path}: {exc}") from exc
    if marker.workspace_version != WORKSPACE_VERSION:
        raise WorkspaceError(
            f"unsupported Workspace version {marker.workspace_version} at {root}; "
            f"this runtime opens version {WORKSPACE_VERSION}"
        )
    _check_combination(marker.purpose, marker.data_class)
    return Workspace(root, marker)
