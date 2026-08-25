from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..infrastructure.paths import relative_within, resolve_within


class PathConfigurationError(RuntimeError):
    """The fixed application directory layout is unsafe."""


ROOT_NAMES = ("knowledge_root", "artifacts_root", "temp_root", "logs_root")


@dataclass(frozen=True)
class AppPaths:
    """Fixed paths below one application root; no marker or selectable root."""

    root: Path
    knowledge_root: Path
    artifacts_root: Path
    temp_root: Path
    logs_root: Path

    @classmethod
    def from_root(cls, root: Path) -> AppPaths:
        resolved_root = Path(root).resolve()
        if not resolved_root.is_dir():
            raise PathConfigurationError(f"application root does not exist: {resolved_root}")
        values = {
            "knowledge_root": resolved_root,
            "artifacts_root": resolved_root / "artifacts",
            "temp_root": resolved_root / "tmp",
            "logs_root": resolved_root / "logs",
        }
        resolved: dict[str, Path] = {}
        for name, candidate in values.items():
            if name != "knowledge_root" and candidate.is_symlink():
                raise PathConfigurationError(
                    f"application path {name} may not be a symlink: {candidate}"
                )
            try:
                resolved[name] = resolve_within(resolved_root, candidate)
            except ValueError as exc:
                raise PathConfigurationError(
                    f"application path {name} escapes the project root: {candidate}"
                ) from exc
        for directory in (resolved["artifacts_root"], resolved["temp_root"], resolved["logs_root"]):
            directory.mkdir(parents=True, exist_ok=True)
        return cls(root=resolved_root, **resolved)

    def relative(self, path: Path) -> str:
        if not Path(path).is_absolute():
            raise PathConfigurationError(f"path is outside the project root: {path}")
        try:
            return relative_within(self.root, path).as_posix()
        except ValueError as exc:
            raise PathConfigurationError(f"path is outside the project root: {path}") from exc
