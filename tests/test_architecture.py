"""The layering rule, enforced on the import graph rather than by review.

`domain <- application <- infrastructure / cli / runtime`: dependencies point
inward. These tests are the M1 acceptance criterion that domain and application
code carries no FastAPI, SQLite, filesystem-layout, browser, or provider HTTP
dependency, expressed so it keeps holding as later milestones add code.
"""

from __future__ import annotations

import ast
import re
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
    "infrastructure/migration.py: imports subprocess",
}

PERSISTENCE_KNOWN_OFFENDERS = {"migration.py", "legacy_source.py"}
SQL_STATEMENT = re.compile(
    r"\b(?:SELECT\b[\s\S]*\bFROM|INSERT\s+INTO|UPDATE\b[\s\S]*\bSET|DELETE\s+FROM|CREATE\s+(?:TABLE|INDEX|TRIGGER)|"
    r"ALTER\s+TABLE|DROP\s+(?:TABLE|INDEX|TRIGGER))\b",
    re.IGNORECASE,
)


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


def _direct_validation_report_calls(path: Path) -> list[int]:
    """Direct model construction sites, excluding the sanctioned factory call."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constructor_names = {"ValidationReport"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        constructor_names.update(
            alias.asname or alias.name
            for alias in node.names
            if alias.name == "ValidationReport"
        )
    found: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in constructor_names:
            found.append(node.lineno)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "ValidationReport":
            found.append(node.lineno)
    return found


def _sql_string_lines(path: Path) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and SQL_STATEMENT.search(node.value)
    ]


def _containment_test_lines(path: Path) -> list[int]:
    """Find independent containment predicates, not relative path formatting."""
    found: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and node.attr == "parents":
            found.append(node.lineno)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "is_relative_to"
        ):
            found.append(node.lineno)
    return found


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


def test_sqlite_and_sql_are_owned_by_persistence() -> None:
    """New SQLite access lands in persistence; only audited legacy adapters remain."""
    offenders: list[str] = []
    for path in _modules("infrastructure"):
        relative = path.relative_to(ENGINE / "infrastructure").as_posix()
        if relative.startswith("persistence/"):
            continue
        if relative in PERSISTENCE_KNOWN_OFFENDERS:
            continue
        if any(name == "sqlite3" for name, _line in _imports(path)):
            offenders.append(f"{relative}: imports sqlite3")
        offenders.extend(
            f"{relative}:{line} contains SQL"
            for line in _sql_string_lines(path)
        )
        offenders.extend(
            f"{relative}:{line} issues PRAGMA"
            for line, source in _code_lines(path)
            if "PRAGMA" in source
        )
    assert not offenders, offenders


def test_path_containment_has_one_implementation() -> None:
    owner = ENGINE / "infrastructure/paths.py"
    assert owner.is_file()
    offenders = [
        f"{path.relative_to(ENGINE)}:{line} implements containment"
        for path in sorted(ENGINE.rglob("*.py"))
        if path != owner
        for line in _containment_test_lines(path)
    ]
    assert not offenders, offenders


def test_numbered_migrations_are_registered_once() -> None:
    migration_dir = ENGINE / "infrastructure/persistence/migrations"
    if not migration_dir.exists():
        return
    files = sorted(migration_dir.glob("*.sql"))
    assert files
    numbered: dict[str, str] = {}
    for path in files:
        match = re.fullmatch(r"(\d{4})_[a-z0-9_]+\.sql", path.name)
        assert match, f"unnumbered migration: {path.name}"
        assert match.group(1) not in numbered, (
            f"duplicate migration number {match.group(1)}: "
            f"{numbered.get(match.group(1))}, {path.name}"
        )
        numbered[match.group(1)] = path.name

    from cv_engine.infrastructure.persistence.schema import registered_migration_names

    registered = registered_migration_names()
    assert len(registered) == len(set(registered)), "migration runner registers a file twice"
    assert registered == [path.name for path in files], (
        f"migration files and runner registry differ: files={[p.name for p in files]} "
        f"registered={registered}"
    )


def test_composite_repository_contains_no_sql() -> None:
    composite = ENGINE / "infrastructure/persistence/composite.py"
    if composite.exists():
        assert not _sql_string_lines(composite)


def test_validation_report_has_one_in_package_construction_authority() -> None:
    """Production callers use the domain factory; fixtures remain unrestricted."""
    offenders = [
        f"{path.relative_to(ENGINE)}:{line} constructs ValidationReport directly"
        for path in sorted(ENGINE.rglob("*.py"))
        if path != ENGINE / "domain/models.py"
        for line in _direct_validation_report_calls(path)
    ]

    assert not offenders, offenders
    models_tree = ast.parse(
        (ENGINE / "domain/models.py").read_text(encoding="utf-8")
    )
    report_class = next(
        node
        for node in models_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ValidationReport"
    )
    factory = next(
        node
        for node in report_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "from_findings"
    )
    assert any(
        isinstance(decorator, ast.Name) and decorator.id == "classmethod"
        for decorator in factory.decorator_list
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "cls"
        for node in ast.walk(factory)
    )
