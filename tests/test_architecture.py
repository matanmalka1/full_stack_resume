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


# Reading or writing a file, and building the name of one, are both storage
# decisions. Listing the calls rather than a couple of known directory names is
# what makes this catch the next violation instead of the last one.
FILESYSTEM_CALLS = (
    ".read_text(",
    ".write_text(",
    ".read_bytes(",
    ".write_bytes(",
    ".open(",
    ".mkdir(",
    ".glob(",
    ".rglob(",
    ".iterdir(",
    ".unlink(",
    ".touch(",
    "open(",
    "shutil.",
    "os.path",
)


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Executable lines only, so prose in a docstring cannot trip a rule."""
    source = path.read_text(encoding="utf-8")
    spans: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            spans.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return [
        (number, line)
        for number, line in enumerate(source.splitlines(), start=1)
        if number not in spans and not line.lstrip().startswith("#")
    ]


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_layer_never_touches_the_filesystem(layer: str) -> None:
    """Neither layer reads, writes, or lists a file.

    This is the rule the earlier, narrower check missed: moving path
    composition out of the application layer only pushed it down into the
    domain, where the same storage knowledge was just as wrong.
    """
    offenders = [
        f"{path.name}:{number}: {line.strip()}"
        for path in _modules(layer)
        for number, line in _code_lines(path)
        if any(call in line for call in FILESYSTEM_CALLS)
    ]
    assert not offenders, offenders


def _joined_path_literals(path: Path) -> list[int]:
    """Lines where a name is divided by a string — i.e. a path is being built.

    Matched on the syntax tree rather than the text so that `"a/b".rsplit("/")`
    and `"https://..."` are not mistaken for layout.
    """
    found: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        for side in (node.left, node.right):
            if isinstance(side, ast.JoinedStr) or (
                isinstance(side, ast.Constant) and isinstance(side.value, str)
            ):
                found.append(node.lineno)
    return found


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_layer_composes_no_storage_layout(layer: str) -> None:
    """Neither layer builds a location out of names it knows.

    A path joined to a literal is a layout decision, wherever it happens: it
    hard-codes where something lives into code that is supposed to only decide
    what it means.
    """
    offenders = [
        f"{path.name}:{line}"
        for path in _modules(layer)
        for line in _joined_path_literals(path)
    ]
    offenders += [
        f"{path.name}:{number}: {line.strip()}"
        for path in _modules(layer)
        for number, line in _code_lines(path)
        if "artifacts_root" in line or "knowledge_root" in line or "base_dir" in line
    ]
    assert not offenders, offenders


def test_domain_modules_never_import_the_workspace() -> None:
    """Domain code receives what it needs; it does not resolve locations."""
    offenders = [
        f"{path.name}:{line}"
        for path in _modules("domain")
        for name, line in _imports(path)
        if name == "runtime"
    ]
    assert not offenders, offenders
