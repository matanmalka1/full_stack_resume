"""The layering rule, enforced on the import graph rather than by review.

`domain <- application <- infrastructure / cli / runtime`: dependencies point
inward. These tests are the M1 acceptance criterion that domain and application
code carries no FastAPI, SQLite, filesystem-layout, browser, or provider HTTP
dependency, expressed so it keeps holding as later milestones add code.
"""

from __future__ import annotations

import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "cv_engine"

FORBIDDEN_EXTERNAL = {
    "domain": {"sqlite3", "fastapi", "playwright", "urllib", "uvicorn", "httpx", "requests"},
    "application": {"sqlite3", "fastapi", "playwright", "urllib", "uvicorn", "httpx", "requests"},
}
ALLOWED_INTERNAL = {
    "domain": {"domain", "util"},
    "application": {"domain", "application", "util"},
}

# Known boundary debt from docs/v2-architecture-audit.md. New entries are not
# permitted. Stages remove entries as they move the owning policy inward.
ARCHITECTURE_DEBT_ALLOWLIST = {
    "cli.py: imports infrastructure.db",
    "infrastructure/migration.py: imports subprocess",
}


def _modules(package: str) -> list[Path]:
    """Every module in the layer, subpackages included.

    Recursive because a layer may group its modules into packages; a rule that
    only saw the top level would quietly stop covering code the moment it moved
    one directory down.
    """
    return sorted((ENGINE / package).rglob("*.py"))


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


def _defines_application_status_transition_table(path: Path) -> bool:
    """Whether a module assigns a mapping whose policy values name ApplicationStatus."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        if any(
            isinstance(child, ast.Name) and child.id == "ApplicationStatus"
            for child in ast.walk(node.value)
        ):
            return True
    return False


def _imports_relative_module(path: Path, module: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == module
        for node in ast.walk(tree)
    )


def test_domain_and_application_dependencies_point_inward() -> None:
    """Report every dependency and storage-boundary violation in one contract."""
    offenders: list[str] = []
    internal_layers = {"domain", "application", "infrastructure", "runtime", "cli"}

    for layer in ("domain", "application"):
        allowed = ALLOWED_INTERNAL[layer] | {"__own_package__"}
        for path in _modules(layer):
            offenders.extend(
                f"{path.relative_to(ENGINE)}:{line} imports forbidden {name}"
                for name, line in _imports(path)
                if name in FORBIDDEN_EXTERNAL[layer]
                or (name in internal_layers and name not in allowed)
            )
            offenders.extend(
                f"{path.relative_to(ENGINE)}:{number} touches filesystem: {line.strip()}"
                for number, line in _code_lines(path)
                if any(call in line for call in FILESYSTEM_CALLS)
            )
            offenders.extend(
                f"{path.relative_to(ENGINE)}:{line} composes storage layout"
                for line in _joined_path_literals(path)
            )
            offenders.extend(
                f"{path.relative_to(ENGINE)}:{number} names storage layout: {line.strip()}"
                for number, line in _code_lines(path)
                if "artifacts_root" in line or "knowledge_root" in line or "base_dir" in line
            )

    assert not offenders, offenders


def test_known_outer_layer_policy_debt_does_not_grow() -> None:
    """Cover CLI, infrastructure, runtime, and compat policy boundaries.

    The allowlist is deliberately explicit: it records A2, A6, and A24 while
    making any new instance fail. As staged work removes an offender, its entry
    is removed from the allowlist; entries may never be added.
    """
    offenders: set[str] = set()
    cli = ENGINE / "cli.py"
    if _imports_relative_module(cli, "infrastructure.db"):
        offenders.add("cli.py: imports infrastructure.db")

    for path in sorted(ENGINE.rglob("*.py")):
        relative = path.relative_to(ENGINE).as_posix()
        if any(name == "subprocess" for name, _line in _imports(path)):
            offenders.add(f"{relative}: imports subprocess")
        if (
            not relative.startswith("domain/")
            and _defines_application_status_transition_table(path)
        ):
            offenders.add(f"{relative}: defines an ApplicationStatus transition table")

    unexpected = offenders - ARCHITECTURE_DEBT_ALLOWLIST
    assert not unexpected, sorted(unexpected)
