"""The layering rule, enforced on the import graph rather than by review.

`domain <- application <- infrastructure / api / runtime / worker`: dependencies point
inward. These tests are the M1 acceptance criterion that domain and application
code carries no FastAPI, persistence-library, filesystem-layout, browser, or provider HTTP
dependency, expressed so it keeps holding as later milestones add code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "cv_engine"

FORBIDDEN_EXTERNAL = {
    "domain": {
        "sqlalchemy",
        "psycopg",
        "fastapi",
        "playwright",
        "urllib",
        "uvicorn",
        "httpx",
        "requests",
    },
    "application": {
        "sqlalchemy",
        "psycopg",
        "fastapi",
        "playwright",
        "urllib",
        "uvicorn",
        "httpx",
        "requests",
    },
    # The API is the one layer that may hold FastAPI. It may not hold storage,
    # a browser, or provider HTTP: reaching any of those from a router is how
    # business logic arrives there.
    "api": {"sqlalchemy", "psycopg", "playwright", "urllib", "requests"},
}
ALLOWED_INTERNAL = {
    "domain": {"domain", "util"},
    "application": {"domain", "application", "util"},
    # `api -> application`, and nothing outward of it. The composition root in
    # `runtime` builds the services and hands them in, so `api` never imports
    # `runtime` or `infrastructure`. `domain` is allowed here for the
    # package as a whole and forbidden inside `routers/`, which is checked
    # separately below.
    "api": {"domain", "application", "api", "util"},
    # An adapter implements the ports the inner layers declare; it does not
    # import the composition root that builds it. `runtime` is the layer that
    # wires adapters together, so an `infrastructure -> runtime` import makes
    # the two packages mutually dependent and puts a real import cycle one
    # module away. Where an adapter needs part of a runtime object, it declares
    # the members it uses as a local Protocol, as `PayloadStore` and
    # `FilesystemArtifactStore` both do.
    "infrastructure": {"domain", "application", "infrastructure", "util"},
}

# Known boundary debt. New entries are not
# permitted. Stages remove entries as they move the owning policy inward. A2, A6, and
# A24 are all closed; the set stays so a regression fails instead of quietly seeding a
# new allowlist.
ARCHITECTURE_DEBT_ALLOWLIST: set[str] = set()

# Every non-persistence module allowed to touch the database libraries. The set
# stays empty so a new adapter leak fails instead of creating a fresh exception.
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

    A layer that moves between a single module and a package must keep the same
    coverage without the check being rewritten by hand for the new shape.
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
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
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
    from cv_engine.runtime.paths import ROOT_NAMES

    # The application's root names, read from their one definition, plus the
    # one storage-layout parameter name (`base_dir`, in infrastructure/knowledge.py)
    # that predates these roots and is not one of them. A hand-picked
    # subset of ROOT_NAMES would silently stop covering a root nobody remembered
    # to add to this list; reading the tuple itself cannot fall out of date.
    storage_layout_names = set(ROOT_NAMES) | {"base_dir"}

    offenders: list[str] = []
    internal_layers = {"domain", "application", "infrastructure", "api", "runtime", "worker"}

    for layer in ("domain", "application", "api"):
        allowed = ALLOWED_INTERNAL[layer] | {"__own_package__"}
        for path in _modules(layer):
            offenders.extend(
                f"{path.relative_to(ENGINE)}:{line} imports forbidden {name}"
                for name, line in _imports(path)
                if name in FORBIDDEN_EXTERNAL[layer]
                or (name in internal_layers and name not in allowed)
            )
            if layer == "api":
                # Storage-layout rules below are about domain and application
                # purity. The API's own storage rule is that it cannot import
                # `infrastructure` at all, which the import check above covers.
                continue
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


def test_infrastructure_does_not_import_its_composition_root() -> None:
    """Adapters point inward only: no `infrastructure -> runtime / api / worker`.

    The inward test above iterates `domain`, `application`, and `api`, because
    its other half asserts storage purity and `infrastructure` is the layer
    that legitimately owns storage. That left infrastructure's own outbound
    edges unchecked, which is how `FilesystemArtifactStore` came to import
    `runtime.paths`. This check is the import half alone, derived from the
    package tree rather than a file list, and it carries no exception set: a
    new outward edge fails here rather than arriving with an allowlist.
    """
    allowed = ALLOWED_INTERNAL["infrastructure"] | {"__own_package__"}
    internal_layers = {"domain", "application", "infrastructure", "api", "runtime", "worker"}

    offenders = [
        f"{path.relative_to(ENGINE)}:{line} imports {name}"
        for path in _layer_modules("infrastructure")
        for name, line in _imports(path)
        if name in internal_layers and name not in allowed
    ]
    assert not offenders, offenders


def test_known_outer_layer_policy_debt_does_not_grow() -> None:
    """Cover the outer layers' policy boundaries.

    The allowlist is now empty: A2, A6, and A24 are closed. It stays as an
    empty set rather than being deleted, so a re-introduced offender fails
    here instead of arriving with a fresh allowlist of its own.

    `worker` is the process host that is not the API: a host that reached past
    the composition root into the database directly is the boundary this rule
    exists to catch.
    """
    offenders: set[str] = set()
    for path in _layer_modules("worker"):
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


def test_database_libraries_and_sql_are_owned_by_persistence() -> None:
    """Database access lands in persistence; there are no remaining exceptions."""
    offenders: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        relative = path.relative_to(ENGINE).as_posix()
        if relative.startswith("infrastructure/persistence/"):
            continue
        if relative.removeprefix("infrastructure/") in PERSISTENCE_KNOWN_OFFENDERS:
            continue
        for name, line in _imports(path):
            if name in {"sqlalchemy", "psycopg"}:
                offenders.append(f"{relative}:{line} imports {name}")
        offenders.extend(f"{relative}:{line} contains SQL" for line in _sql_string_lines(path))
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

    # Approved HTML is a different transport policy over the existing verified
    # artifact delivery, not a second verifier in the router or service. Keep
    # these two delegation edges explicit: Stage B previously regressed when an
    # API helper reimplemented storage checks beside the application service.
    approved_router = (ENGINE / "api/routers/approved_revisions.py").read_text(encoding="utf-8")
    rendering_service = (ENGINE / "application/services/rendering.py").read_text(encoding="utf-8")
    assert "services.rendering.preview_approved_html(" in approved_router
    assert "return self.download_artifact(html_artifact_version_id)" in rendering_service
    # Read the code, not the prose. This scanned the whole file once, so a
    # docstring explaining what `content_hash` means to a client failed as
    # though the router were computing one.
    approved_router_code = "\n".join(
        line for _number, line in _code_lines(ENGINE / "api/routers/approved_revisions.py")
    )
    assert not any(
        token in approved_router_code
        for token in ("content_hash", ".resolve(", ".read_bytes(", ".is_file(")
    )


def test_numbered_migrations_are_registered_once() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ENGINE.parent / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    revisions = list(scripts.walk_revisions())
    identifiers = [revision.revision for revision in revisions]
    files = set((ENGINE.parent / "alembic/versions").glob("[0-9][0-9][0-9][0-9]_*.py"))

    assert len(scripts.get_heads()) == 1, "Alembic must have exactly one head"
    assert len(identifiers) == len(set(identifiers)), "Alembic registers a revision twice"
    assert {Path(revision.path) for revision in revisions} == files
    assert all(
        Path(revision.path).name.startswith(f"{revision.revision}_") for revision in revisions
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


def test_api_is_not_imported_by_the_layers_it_serves() -> None:
    """`api` is a client of the application, never a dependency of it.

    The direction is `api -> application` and `runtime -> api`. An import
    pointing the other way - a service reaching for an HTTP schema, a repository
    raising something defined in a router - is how a transport concern becomes
    load-bearing inside the layers the API is meant to serve.
    """
    offenders: list[str] = []
    for layer in ("domain", "application", "infrastructure", "worker"):
        for path in _layer_modules(layer):
            offenders.extend(
                f"{path.relative_to(ENGINE)}:{line} imports api from the {layer} layer"
                for target, line in _resolved_import_modules(path)
                if target == "api" or target.startswith("api.")
            )
    assert not offenders, offenders


def test_routers_hold_no_domain_types() -> None:
    """The derived form of "routers contain no business logic" (M3 §5.4, item 4).

    HTTP schemas are specified as separate from domain and persistence types, so
    a router with nothing but transport in it has no reason to name a domain
    type. One that does is either building a domain object, inspecting one, or
    serialising one straight to the wire - the three ways business logic gets
    into a router.

    A substring check on the word "logic" could not find any of that. An import
    edge can, and it fails at the designated place instead of arriving as an ad
    hoc exemption somewhere else.
    """
    routers = ENGINE / "api/routers"
    assert routers.is_dir(), "the api routers package must exist"
    offenders = [
        f"{path.relative_to(ENGINE)}:{line} imports domain type {target}"
        for path in sorted(routers.rglob("*.py"))
        for target, line in _resolved_import_modules(path)
        if target == "domain" or target.startswith("domain.")
    ]
    assert not offenders, offenders


def _raises_argument_names(call: ast.Call) -> set[str]:
    """Every exception name a `pytest.raises(...)` call names.

    Both spellings, because they are equally common and only one of them is
    obvious: `pytest.raises(KeyError)` and `pytest.raises((KeyError, OSError))`.
    An audit that only understood the first missed two live assertions during
    M3 Stage A, which is why this reads the tuple as well.
    """
    if not call.args:
        return set()
    first = call.args[0]
    elements = first.elts if isinstance(first, ast.Tuple) else [first]
    return {node.id for node in elements if isinstance(node, ast.Name)}


def test_no_test_asserts_a_bare_builtin_from_a_repository() -> None:
    """Tests must pin the refusal contract, not the builtin it replaced.

    A repository refusal is `UnknownRecord`, `StateConflict`, `LineageBroken`,
    or another member of the taxonomy. `pytest.raises(KeyError)` around a
    repository call asserts a contract that no longer exists; it fails loudly
    once, and then someone is tempted to widen the tuple instead of fixing the
    assertion.

    The repository methods are discovered from the persistence package rather
    than listed, so a new method that raises the taxonomy is covered the day it
    is written.
    """
    from cv_engine.application import errors as taxonomy

    taxonomy_names = {
        name
        for name in dir(taxonomy)
        if isinstance(getattr(taxonomy, name), type)
        and issubclass(getattr(taxonomy, name), taxonomy.ApplicationError)
    }
    persistence = ENGINE / "infrastructure/persistence"
    raising: set[str] = set()
    for path in sorted(persistence.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Raise) or sub.exc is None:
                    continue
                raised = sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc
                if isinstance(raised, ast.Name) and raised.id in taxonomy_names:
                    raising.add(node.name)
    assert raising, "no persistence method raises the taxonomy; the discovery is broken"

    offenders: list[str] = []
    for path in sorted(Path(__file__).parent.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            named: set[str] = set()
            for item in node.items:
                expr = item.context_expr
                if (
                    isinstance(expr, ast.Call)
                    and isinstance(expr.func, ast.Attribute)
                    and expr.func.attr == "raises"
                ):
                    named |= _raises_argument_names(expr)
            if not named & {"KeyError", "ValueError"}:
                continue
            body = ast.Module(body=node.body, type_ignores=[])
            called = sorted(
                sub.func.attr
                for sub in ast.walk(body)
                if isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in raising
            )
            if called:
                offenders.append(
                    f"{path.name}:{node.lineno} asserts a bare builtin over {', '.join(called)}"
                )
    assert not offenders, offenders


def test_carry_forward_of_accepted_gaps_has_one_implementation() -> None:
    """No caller may hand a plan write a whole acceptance list.

    This replaces an earlier guard that required every plan writer to *name*
    what happens to accepted gaps. That guard matched the old design, where the
    column defaulted to empty and forgetting silently retracted decisions. The
    repository now reads, merges and writes the standing acceptances inside the
    write transaction under the Application lock, so forgetting is the safe
    default and the old guard would only fail honest callers.

    What is dangerous now is the opposite: a caller that assembles the list and
    passes it in, bypassing the analysis check and the lock. That is exactly how
    a plan for one analysis came to inherit another's. A writer may say what it
    *adds* (`new_acceptances`); it may not say what the plan ends up holding.

    Reading `accepted_gaps` stays free - the gate, the model validator and the
    decision record all legitimately do - because reading cannot lose a write.
    """
    root = Path(__file__).resolve().parents[1] / "cv_engine"
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name not in {"create_selection_plan", "_insert_selection_plan"}:
                continue
            if any(keyword.arg == "accepted_gaps" for keyword in node.keywords):
                if path.name == "preparation.py":
                    continue
                offenders.append(f"{path.relative_to(root).as_posix()}:{node.lineno}")
    assert not offenders, (
        "these hand a plan write its whole acceptance list; only the repository "
        f"may do that, under the lock and the analysis check: {offenders}"
    )


def test_every_selection_plan_write_takes_the_application_lock_first() -> None:
    """The lock has to precede the read it protects, in every writer.

    `create_selection_plan` reads the standing acceptances and allocates the
    version number; both have to happen under the Application row lock, or two
    writers merge onto the same plan and one acceptance is lost. `save_analysis`
    inserts a plan too, so it locks as well - a path that skips the lock is not
    serialized by the others taking it.

    Asserted on the order of statements, not merely on the lock being present
    somewhere in the function: locking after the read would satisfy a presence
    check and protect nothing.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "cv_engine"
        / "infrastructure"
        / "persistence"
        / "preparation.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    writers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name != "_insert_selection_plan"
        and "_insert_selection_plan(" in (ast.get_source_segment(source, node) or "")
    ]
    assert {node.name for node in writers} == {"save_analysis", "create_selection_plan"}, (
        "a new selection-plan writer appeared; it must lock before it reads"
    )
    for node in writers:
        calls = [
            (inner.lineno, getattr(inner.func, "attr", None) or getattr(inner.func, "id", None))
            for inner in ast.walk(node)
            if isinstance(inner, ast.Call)
        ]
        lock = next((line for line, name in calls if name == "_lock_application"), None)
        insert = next((line for line, name in calls if name == "_insert_selection_plan"), None)
        standing = next((line for line, name in calls if name == "_standing_acceptances"), None)
        assert lock is not None, f"{node.name} writes a plan without taking the lock"
        assert insert is not None and lock < insert, f"{node.name} locks after inserting"
        if standing is not None:
            assert lock < standing, f"{node.name} reads the standing acceptances before locking"
