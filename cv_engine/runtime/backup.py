"""Workspace backup and restore.

v1 is a frozen archive and is never migrated, so nothing here looks backwards.
What it protects is what v2 accumulates and cannot regenerate: approved
revisions, submitted artifacts, and job snapshots of postings that later
disappear from the web. Everything else the engine produces — drafts,
selections, renders, projections — costs a re-run, not a backup.

There is deliberately no manifest. The artifact hashes already live in
`artifact_versions` and the database checks itself with `PRAGMA
integrity_check`; a second hash list maintained beside them could only drift
away from them and would then have to be adjudicated against them. The proof a
backup is good is that it opens: restore into a new directory, load the
Workspace, and reconcile.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..infrastructure.paths import is_within
from ..infrastructure.persistence import backup_database
from .workspace import KNOWLEDGE_DIRS, MARKER_NAME, Workspace, load_workspace

# `tmp` and `logs` are excluded on purpose. Temporary files are mid-operation
# scratch whose meaning does not survive the process that wrote them, and logs
# are diagnostics about a run rather than state the Workspace needs to reopen.
EXCLUDED_ROOTS = ("temp_root", "logs_root")


class BackupError(RuntimeError):
    """The backup or restore could not be performed safely."""


@dataclass(frozen=True)
class BackupReport:
    root: Path
    database: Path
    directories: tuple[str, ...]
    file_count: int

    def describe(self) -> dict[str, object]:
        return {
            "backup_root": str(self.root),
            "database": str(self.database),
            "directories": list(self.directories),
            "file_count": self.file_count,
        }


def _count_files(root: Path) -> int:
    return sum(1 for path in root.rglob("*") if path.is_file())


def _require_empty_target(target: Path, what: str) -> None:
    if target.exists() and any(target.iterdir()):
        raise BackupError(
            f"refusing to write a {what} into a non-empty directory: {target}. "
            "Always target a new directory so an existing Workspace cannot be overlaid."
        )


def _durable_tree_ignore(database_path: Path) -> Callable[[str, list[str]], set[str]]:
    database_files = {
        database_path,
        Path(f"{database_path}-shm"),
        Path(f"{database_path}-wal"),
    }

    def ignore(directory: str, names: list[str]) -> set[str]:
        directory_path = Path(directory).resolve()
        ignored = set(shutil.ignore_patterns("*.sqlite3*")(directory, names))
        ignored.update(
            name for name in names if directory_path / name in database_files
        )
        return ignored

    return ignore


def backup_workspace(
    workspace: Workspace, target: Path, *, database_path: Path | None = None
) -> BackupReport:
    """Copy a Workspace's durable state into a new directory.

    The database goes through the SQLite backup API rather than a file copy, so
    the archive is transactionally consistent even while the Workspace is in
    use. Everything else is plain files and copies as such.
    """
    target = Path(target).resolve()
    source_database = Path(database_path or workspace.database_path).resolve()
    if not is_within(workspace.root, source_database):
        raise BackupError(f"database to back up escapes its Workspace: {source_database}")
    if is_within(workspace.root, target):
        raise BackupError(f"a backup may not be written inside its own Workspace: {target}")
    _require_empty_target(target, "backup")
    target.mkdir(parents=True, exist_ok=True)

    shutil.copy2(workspace.root / MARKER_NAME, target / MARKER_NAME)

    copied: list[str] = []
    for name in KNOWLEDGE_DIRS:
        source = workspace.knowledge_root / name
        if source.is_dir():
            shutil.copytree(source, target / name)
            copied.append(name)

    for name in ("state_root", "artifacts_root"):
        source: Path = getattr(workspace, name)
        if not source.is_dir():
            continue
        relative = source.relative_to(workspace.root)
        shutil.copytree(
            source,
            target / relative,
            ignore=_durable_tree_ignore(source_database),
        )
        copied.append(relative.as_posix())

    # A CLI/environment database override is not durable Workspace metadata,
    # and the root config file is intentionally outside the copied knowledge
    # directories. Normalize the consistent SQLite snapshot to the Workspace's
    # default database location so every restore opens the protected state
    # without needing the process that made the backup to reproduce an override.
    database = target / workspace.database_path.relative_to(workspace.root)
    backup_database(source_database, database)

    return BackupReport(
        root=target,
        database=database,
        directories=tuple(copied),
        file_count=_count_files(target),
    )


def restore_workspace(backup: Path, target: Path) -> Workspace:
    """Restore a backup into a new directory and open it.

    Restoring never overlays an existing Workspace: a restore that could write
    over live state would make the backup itself a hazard. The returned
    Workspace is loaded through the normal fail-closed path, so a restore that
    produced something unopenable fails here rather than at first use.
    """
    backup = Path(backup).resolve()
    if not (backup / MARKER_NAME).is_file():
        raise BackupError(f"not a Workspace backup: {backup} has no {MARKER_NAME}")
    target = Path(target).resolve()
    if target == backup:
        raise BackupError(f"restore target may not be the backup itself: {target}")
    _require_empty_target(target, "restore")

    shutil.copytree(backup, target, dirs_exist_ok=True)
    return load_workspace(target)
