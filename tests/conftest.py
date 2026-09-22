from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import cast

import pytest

import cv_engine

SOURCE_ROOT = Path(__file__).resolve().parent.parent

pytest_plugins = (
    "fixtures.api",
    "fixtures.database",
    "fixtures.knowledge",
    "fixtures.rendering",
    "fixtures.workflows",
)


# The v1 worktree ships an editable install of this package, whose finder
# resolves any cv_engine submodule missing here to the v1 tree. Checking the
# top-level package is not enough: a single stale relative import is invisible
# that way, and every later result is then partly v1 code.
def _foreign_modules() -> dict[str, str]:
    return {
        name: cast(str, module.__file__)
        for name, module in sorted(sys.modules.items())
        if name.startswith("cv_engine")
        and getattr(module, "__file__", None)
        and SOURCE_ROOT not in Path(cast(str, module.__file__)).resolve().parents
    }


_IMPORTED_FROM = Path(cast(str, cv_engine.__file__)).resolve().parent.parent
assert _IMPORTED_FROM == SOURCE_ROOT, (
    f"tests import cv_engine from {_IMPORTED_FROM}, not the worktree under test ({SOURCE_ROOT})"
)
assert not _foreign_modules(), (
    f"cv_engine modules loaded from another worktree: {_foreign_modules()}"
)

# Only acceptance tests that validate real layout/PDF behavior use this fixture.
# Integrity tests create the same artifact/version graph with a deterministic
# renderer double, so Chromium is not paid for when the behavior under test is
# hashes, linkage, lifecycle, or database state.
BROWSER_FIXTURES = frozenset({"render_validator"})


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items) -> None:
    for item in items:
        if BROWSER_FIXTURES & set(item.fixturenames):
            item.add_marker("browser")


def pytest_sessionfinish(session, exitstatus) -> None:
    """Fail the run if any cv_engine module came from another worktree.

    Checked at the end as well as at import, because modules load lazily: a
    stale relative import inside a rarely exercised path would otherwise only
    show up as a mysteriously passing test.
    """
    foreign = _foreign_modules()
    if foreign:
        session.exitstatus = 1
        raise pytest.UsageError(f"cv_engine modules loaded from another worktree: {foreign}")


def pytest_collection_finish(session) -> None:
    """Guard against a reduced run being mistaken for a complete one.

    Rendering, PDF, and ATS checks are acceptance requirements, so an
    environment that claims completeness (CV_REQUIRE_BROWSER=1) must not
    silently drop them.
    """
    if not os.environ.get("CV_REQUIRE_BROWSER"):
        return
    if any(item.get_closest_marker("browser") for item in session.items):
        return
    raise pytest.UsageError(
        "CV_REQUIRE_BROWSER=1 but no browser tests were collected. "
        "Rendering/PDF/ATS coverage is required for a complete run; "
        'drop the "not browser" selection or unset CV_REQUIRE_BROWSER.'
    )
