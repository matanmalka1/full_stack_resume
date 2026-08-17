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
    # The application layer may name the runtime's Workspace value object and
    # the composition root it defers to, but no infrastructure adapter.
    "application": {"domain", "application", "util", "runtime"},
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


def test_the_composition_root_is_the_only_application_link_to_infrastructure() -> None:
    """The façade may defer to composition, but only inside a function body.

    A module-level import would make the application layer depend on every
    adapter at import time, which is exactly what the boundary is for.
    """
    workflow = ENGINE / "application" / "workflow.py"
    tree = ast.parse(workflow.read_text(encoding="utf-8"))
    module_level = {
        node.module or ""
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert not any("composition" in name or "infrastructure" in name for name in module_level)


def test_domain_modules_never_import_the_workspace() -> None:
    """Domain code receives paths; it does not resolve them."""
    offenders = [
        f"{path.name}:{line}"
        for path in _modules("domain")
        for name, line in _imports(path)
        if name == "runtime"
    ]
    assert not offenders, offenders
