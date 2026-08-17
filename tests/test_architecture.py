"""The layering rule, enforced on the import graph rather than by review.

`domain <- application <- infrastructure / cli / runtime`: dependencies point
inward. These tests are the M1 acceptance criterion that domain and application
code carries no FastAPI, SQLite, filesystem-layout, browser, or provider HTTP
dependency, expressed so it keeps holding as later milestones add code.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


ENGINE = Path(__file__).resolve().parent.parent / "cv_engine"

FORBIDDEN_EXTERNAL = {
    "domain": {"sqlite3", "fastapi", "playwright", "urllib", "uvicorn", "httpx", "requests"},
    "application": {"sqlite3", "fastapi", "playwright", "urllib", "uvicorn", "httpx", "requests"},
}
ALLOWED_INTERNAL = {
    "domain": {"domain", "util"},
    "application": {"domain", "application", "util"},
}


def _modules(package: str) -> list[Path]:
    return sorted((ENGINE / package).glob("*.py"))


def _imports(path: Path) -> list[tuple[str, int]]:
    """Every imported module name, resolved to its top-level package name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name.split(".")[0], node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                found.append(((node.module or "").split(".")[0], node.lineno))
            elif node.level == 1:
                found.append(("__own_package__", node.lineno))
            else:
                found.append(((node.module or "").split(".")[0], node.lineno))
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_EXTERNAL))
def test_layer_imports_no_infrastructure_technology(layer: str) -> None:
    offenders = [
        f"{path.name}:{line} imports {name}"
        for path in _modules(layer)
        for name, line in _imports(path)
        if name in FORBIDDEN_EXTERNAL[layer]
    ]
    assert not offenders, offenders


@pytest.mark.parametrize("layer", sorted(ALLOWED_INTERNAL))
def test_layer_depends_only_inward(layer: str) -> None:
    allowed = ALLOWED_INTERNAL[layer] | {"__own_package__"}
    offenders = [
        f"{path.name}:{line} imports cv_engine.{name}"
        for path in _modules(layer)
        for name, line in _imports(path)
        if name in {"domain", "application", "infrastructure", "runtime", "cli"}
        and name not in allowed
    ]
    assert not offenders, offenders


def test_no_application_module_reaches_the_composition_root() -> None:
    """Composition belongs to the runtime, not to the layer it wires up.

    The v1 compatibility façade lives outside the layered packages precisely so
    it can build services without dragging that dependency into application
    code.
    """
    offenders = [
        f"{path.name}:{line}"
        for path in _modules("application")
        for name, line in _imports(path)
        if name in {"runtime", "infrastructure"}
    ]
    assert not offenders, offenders


def test_application_composes_no_storage_paths() -> None:
    """Layout is asked for through the artifact store, never assembled here."""
    offenders = [
        f"{path.name}:{number}: {line.strip()}"
        for path in _modules("application")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if "artifacts_root" in line or '"working"' in line or "mkdir(" in line
    ]
    assert not offenders, offenders


def test_domain_modules_never_import_the_workspace() -> None:
    """Domain code receives paths; it does not resolve them."""
    offenders = [
        f"{path.name}:{line}"
        for path in _modules("domain")
        for name, line in _imports(path)
        if name == "runtime"
    ]
    assert not offenders, offenders
