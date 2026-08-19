from __future__ import annotations

from pathlib import Path


def resolve_within(root: Path, candidate: Path | str) -> Path:
    """Resolve ``candidate`` and refuse traversal or a symlink escape from ``root``."""
    resolved_root = Path(root).resolve()
    unresolved = Path(candidate)
    resolved = (
        unresolved.resolve() if unresolved.is_absolute() else (resolved_root / unresolved).resolve()
    )
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"path escapes configured root {resolved_root}: {candidate}")
    return resolved


def is_within(root: Path, candidate: Path | str) -> bool:
    """True when ``candidate`` resolves inside ``root``, ``root`` itself included.

    The predicate form of `resolve_within`, for callers that need to branch on
    containment rather than refuse it. It lives here so containment keeps one
    implementation: a caller writing its own `is_relative_to` would decide
    traversal and symlink escapes separately from this module, and the two
    answers would eventually disagree.
    """
    try:
        resolve_within(root, candidate)
    except ValueError:
        return False
    return True


def relative_within(root: Path, path: Path | str) -> Path:
    """Return a resolved root-relative path, refusing traversal and symlink escapes."""
    resolved_root = Path(root).resolve()
    return resolve_within(resolved_root, path).relative_to(resolved_root)
