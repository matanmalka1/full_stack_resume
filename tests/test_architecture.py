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

# Known boundary debt from docs/v2/records/architecture-audit.md. New entries are not
# permitted. Stages remove entries as they move the owning policy inward. A2, A6, and
# A24 are all closed; the set stays so a regression fails instead of quietly seeding a
# new allowlist.
ARCHITECTURE_DEBT_ALLOWLIST: set[str] = set()

# Every non-persistence module that may still touch SQLite. Deleting the v1 migration
# adapters emptied it, so any new SQLite access outside persistence now fails.
PERSISTENCE_KNOWN_OFFENDERS: set[str] = set()
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


def _layer_modules(name: str) -> list[Path]:
    """The modules that make up a top-level layer, whether it is one file or a package.

    A layer that starts as a single module (`cli.py`) and later becomes a
    package (`cli/`) must keep the same coverage without the check being
    rewritten by hand for the new shape.
    """
    package = ENGINE / name
    if package.is_dir():
        return sorted(package.rglob("*.py"))
    module = ENGINE / f"{name}.py"
    return [module] if module.is_file() else []


def _resolved_import_modules(path: Path) -> list[tuple[str, int]]:
    """Every module this file imports, as a dotted path relative to `cv_engine`.

    Absolute imports of `cv_engine...` are normalized by stripping the prefix.
    Relative imports are resolved against the importing file's own package
    position (mirroring Python's own relative-import rule: level 1 is the
    file's containing package, each further level goes up one more), so a
    check for a target module finds it however many directories separate the
    importing file from the package root. That is what lets a layer move from
    a single module to a package without the check silently losing coverage.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    own_package = path.relative_to(ENGINE).with_suffix("").parts[:-1]
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "cv_engine" or name.startswith("cv_engine."):
                    name = name[len("cv_engine.") :]
                found.append((name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                module = node.module or ""
                if module == "cv_engine" or module.startswith("cv_engine."):
                    module = module[len("cv_engine.") :]
                found.append((module, node.lineno))
            else:
                depth = max(len(own_package) - (node.level - 1), 0)
                base = own_package[:depth]
                target = ".".join((*base, node.module)) if node.module else ".".join(base)
                found.append((target, node.lineno))
    return found


def _direct_validation_report_calls(path: Path) -> list[int]:
    """Direct model construction sites, excluding the sanctioned factory call."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constructor_names = {"ValidationReport"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        constructor_names.update(
            alias.asname or alias.name for alias in node.names if alias.name == "ValidationReport"
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
    from cv_engine.runtime.workspace import ROOT_NAMES

    # The Workspace's own root names, read from their one definition, plus the
    # one storage-layout parameter name (`base_dir`, in infrastructure/knowledge.py)
    # that predates the Workspace roots and is not one of them. A hand-picked
    # subset of ROOT_NAMES would silently stop covering a root nobody remembered
    # to add to this list; reading the tuple itself cannot fall out of date.
    storage_layout_names = set(ROOT_NAMES) | {"base_dir"}

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
                if any(name in line for name in storage_layout_names)
            )

    assert not offenders, offenders


def test_known_outer_layer_policy_debt_does_not_grow() -> None:
    """Cover CLI, infrastructure, runtime, and compat policy boundaries.

    The allowlist is now empty: A2, A6, and A24 are closed. It stays as an
    empty set rather than being deleted, so a re-introduced offender fails
    here instead of arriving with a fresh allowlist of its own.
    """
    offenders: set[str] = set()
    for path in _layer_modules("cli"):
        relative = path.relative_to(ENGINE).as_posix()
        if any(
            target == "infrastructure.db" or target.startswith("infrastructure.db.")
            for target, _line in _resolved_import_modules(path)
        ):
            offenders.add(f"{relative}: imports infrastructure.db")

    for path in sorted(ENGINE.rglob("*.py")):
        relative = path.relative_to(ENGINE).as_posix()
        if any(name == "subprocess" for name, _line in _imports(path)):
            offenders.add(f"{relative}: imports subprocess")
        if not relative.startswith("domain/") and _defines_application_status_transition_table(
            path
        ):
            offenders.add(f"{relative}: defines an ApplicationStatus transition table")

    unexpected = offenders - ARCHITECTURE_DEBT_ALLOWLIST
    assert not unexpected, sorted(unexpected)


def test_sqlite_and_sql_are_owned_by_persistence() -> None:
    """All SQLite access lands in persistence; there are no remaining exceptions."""
    offenders: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        relative = path.relative_to(ENGINE).as_posix()
        if relative.startswith("infrastructure/persistence/"):
            continue
        if relative.removeprefix("infrastructure/") in PERSISTENCE_KNOWN_OFFENDERS:
            continue
        if any(name == "sqlite3" for name, _line in _imports(path)):
            offenders.append(f"{relative}: imports sqlite3")
        offenders.extend(f"{relative}:{line} contains SQL" for line in _sql_string_lines(path))
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
    assert migration_dir.is_dir(), "the registered migration directory must exist"
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


def test_validation_report_has_one_in_package_construction_authority() -> None:
    """Production callers use the domain factory; fixtures remain unrestricted."""
    offenders = [
        f"{path.relative_to(ENGINE)}:{line} constructs ValidationReport directly"
        for path in sorted(ENGINE.rglob("*.py"))
        if path != ENGINE / "domain/models.py"
        for line in _direct_validation_report_calls(path)
    ]

    assert not offenders, offenders
    models_tree = ast.parse((ENGINE / "domain/models.py").read_text(encoding="utf-8"))
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
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "cls"
        for node in ast.walk(factory)
    )


def test_persistence_refuses_through_the_application_taxonomy() -> None:
    """A repository refusal reaches a client as a typed error, not a bare builtin.

    The API has to turn a refusal into an HTTP status, and only the raise site
    knows which refusal it is: a missing row is `UnknownRecord` (404), an edit
    version that moved is `StateConflict` (409), a source that belongs to
    another application is `LineageBroken` (412). Mapping `ValueError` wholesale
    at the boundary would collapse those three into one, so the classification
    is made where the meaning is known and this check keeps it there.

    The exemptions are contract violations by the caller rather than domain
    refusals: passing a UnitOfWork built against another database, or a
    non-positive lease. Those are bugs in calling code, and `ValueError` is the
    right answer to a bug.
    """
    exempt = {
        "base.py:UnitOfWork belongs to another database",
        "preparation.py:UnitOfWork belongs to another database",
        "operations.py:lease_seconds must be positive",
    }
    offenders: list[str] = []
    seen: set[str] = set()
    for path in sorted((ENGINE / "infrastructure/persistence").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            name = call.func if isinstance(call, ast.Call) else call
            if not isinstance(name, ast.Name) or name.id not in {"KeyError", "ValueError"}:
                continue
            first = call.args[0] if isinstance(call, ast.Call) and call.args else None
            literal = first.value if isinstance(first, ast.Constant) else None
            key = f"{path.name}:{literal}"
            seen.add(key)
            if key in exempt:
                continue
            offenders.append(
                f"{path.relative_to(ENGINE)}:{node.lineno} raises bare {name.id}; "
                "use the application taxonomy so the API can classify it"
            )
    assert not offenders, offenders
    # An exemption that stops matching a real raise is an exemption nobody is
    # reading any more. Fail rather than let the list drift out of date.
    assert not (exempt - seen), f"stale exemptions: {sorted(exempt - seen)}"
