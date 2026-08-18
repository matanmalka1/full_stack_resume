from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..runtime.workspace import MARKER_NAME
from ..util import canonical_json, sha256_bytes, sha256_text, utc_now
from .paths import resolve_within


SKIP_DIRECTORIES = frozenset({".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"})


class LegacySourceError(RuntimeError):
    """The legacy source cannot be read under the read-only contract."""


@dataclass(frozen=True)
class LegacyInventory:
    root: str
    captured_at: str
    files: dict[str, str]
    inventory_hash: str

    def describe(self) -> dict[str, object]:
        return {
            "root": self.root,
            "captured_at": self.captured_at,
            "file_count": len(self.files),
            "inventory_hash": self.inventory_hash,
        }


class LegacyV1Source:
    """The only way v2 code may touch an unmarked v1 root.

    The adapter offers no write operation of any kind: no marker, no temporary
    file, no schema upgrade, no database connection that can mutate. Reads are
    bound to an inventory hash, so a source that changed under a migration run
    is detected instead of being silently mixed with the earlier reads.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise LegacySourceError(f"legacy source is not a directory: {self.root}")
        if (self.root / MARKER_NAME).exists():
            raise LegacySourceError(
                f"{self.root} carries a v2 Workspace marker; open it as a Workspace, "
                "not as a legacy migration source"
            )
        self._bound: LegacyInventory | None = None

    @property
    def bound_inventory(self) -> LegacyInventory | None:
        return self._bound

    def inventory(self) -> LegacyInventory:
        """Hash every file under the source and bind subsequent reads to it."""
        files: dict[str, str] = {}
        for path in sorted(self.root.rglob("*")):
            if any(part in SKIP_DIRECTORIES for part in path.relative_to(self.root).parts):
                continue
            if path.is_symlink() or not path.is_file():
                continue
            files[path.relative_to(self.root).as_posix()] = sha256_bytes(path.read_bytes())
        inventory = LegacyInventory(
            root=str(self.root),
            captured_at=utc_now(),
            files=files,
            inventory_hash=sha256_text(canonical_json({"root": self.root.name, "files": files})),
        )
        self._bound = inventory
        return inventory

    @staticmethod
    def _relative_key(relative: str | Path) -> str:
        candidate = Path(relative)
        if candidate.is_absolute():
            raise LegacySourceError(f"legacy reads use source-relative paths: {relative}")
        if any(part in {"..", ""} for part in candidate.parts):
            raise LegacySourceError(f"path escapes the legacy source: {relative}")
        return candidate.as_posix()

    def _resolve(self, relative: str | Path) -> Path:
        candidate = Path(self._relative_key(relative))
        try:
            resolved = resolve_within(self.root, candidate)
        except ValueError as exc:
            raise LegacySourceError(f"path escapes the legacy source: {relative}") from exc
        if not resolved.is_file():
            raise LegacySourceError(f"no such file in the legacy source: {relative}")
        return resolved

    def _require_binding(self, relative: str | Path) -> str:
        key = self._relative_key(relative)
        if self._bound is None:
            raise LegacySourceError("take an inventory before reading the legacy source")
        if key not in self._bound.files:
            raise LegacySourceError(f"file is not part of the bound inventory: {key}")
        return self._bound.files[key]

    def read_bytes(self, relative: str | Path) -> bytes:
        expected = self._require_binding(relative)
        payload = self._resolve(relative).read_bytes()
        actual = sha256_bytes(payload)
        if actual != expected:
            raise LegacySourceError(
                f"legacy source changed during the run: {relative} "
                f"(inventoried {expected[:12]}, read {actual[:12]})"
            )
        return payload

    def read_text(self, relative: str | Path, encoding: str = "utf-8") -> str:
        return self.read_bytes(relative).decode(encoding)

    def open_database(self, relative: str | Path) -> sqlite3.Connection:
        """A connection SQLite itself refuses to write through."""
        self._require_binding(relative)
        path = self._resolve(relative)
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def verify_unchanged(self) -> LegacyInventory:
        """Re-inventory and prove the source is byte-identical to the binding."""
        if self._bound is None:
            raise LegacySourceError("nothing to verify: no inventory has been taken")
        expected = self._bound
        current = self.inventory()
        self._bound = expected
        if current.inventory_hash != expected.inventory_hash:
            added = sorted(set(current.files) - set(expected.files))
            removed = sorted(set(expected.files) - set(current.files))
            changed = sorted(
                key for key in set(current.files) & set(expected.files)
                if current.files[key] != expected.files[key]
            )
            raise LegacySourceError(
                "legacy source is no longer identical to its inventory: "
                f"added={added} removed={removed} changed={changed}"
            )
        return expected
