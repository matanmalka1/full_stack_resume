"""Run the Stage F browser gate against the real ``cv web`` composition.

The database is supplied by the gate command and must already be an empty, upgraded,
disposable PostgreSQL database. Candidate sources are copied to a temporary project so
the browser journey can exercise local object storage and a recoverable renderer failure
without writing into the live project.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import tempfile
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from cv_engine.cli import main
from cv_engine.runtime.web import select_web_endpoint
from cv_engine.infrastructure.persistence import (
    create_database_engine,
    current_database_revision,
)
from cv_engine.infrastructure.persistence.tables import metadata

SOURCE_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = SOURCE_ROOT / "frontend"
PROJECT_MARKER = FRONTEND_ROOT / "test-results" / "stage-f-project-root.txt"
SOURCE_DIRECTORIES = ("base", "profiles", "rendering", "ai", "config")


def _expected_revision() -> str:
    heads = ScriptDirectory.from_config(Config(str(SOURCE_ROOT / "alembic.ini"))).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Stage F requires exactly one Alembic head; found {heads}")
    return heads[0]


def _assert_empty_current_database(database_url: str) -> None:
    engine = create_database_engine(database_url)
    try:
        expected = _expected_revision()
        actual = current_database_revision(engine)
        if actual != expected:
            raise RuntimeError(
                "Stage F database is not upgraded to the current Alembic head "
                f"({actual or 'no revision'} != {expected})"
            )
        with engine.connect() as connection:
            populated = [
                table.name
                for table in metadata.sorted_tables
                if connection.execute(
                    text(f'SELECT COUNT(*) FROM "{table.name}"')
                ).scalar_one()
                != 0
            ]
        if populated:
            raise RuntimeError(
                "Stage F refuses a database that already contains application data "
                f"({', '.join(populated)}); create a fresh disposable PostgreSQL database"
            )
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Stage F could not verify its PostgreSQL database: {exc}") from exc
    finally:
        engine.dispose()


def _assert_port_is_ours(port: int) -> None:
    """Refuse to run unless this process will own the port Playwright watches.

    ``cv web`` reuses a matching existing instance on a version match alone, and
    otherwise falls back to a free port. Either outcome would silently point the
    gate somewhere else: reuse would drive a host bound to a different project and
    database, and the fallback would serve a port Playwright never opens.
    """
    endpoint = select_web_endpoint(preferred_port=port)
    if endpoint.reuse_existing:
        raise RuntimeError(
            f"Stage F refuses to reuse the existing host on port {port}; it serves a "
            "different project and database. Stop it and re-run the gate"
        )
    if endpoint.port != port:
        raise RuntimeError(
            f"Stage F requires port {port}, which another process already holds. "
            "Stop it and re-run the gate"
        )


def _copy_test_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="cv-stage-f-"))
    for directory in SOURCE_DIRECTORIES:
        shutil.copytree(SOURCE_ROOT / directory, root / directory)
    return root


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()

    if os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Stage F requires OPENAI_API_KEY to be unset")
    database_url = os.environ.get("CV_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Stage F requires CV_DATABASE_URL to name a fresh disposable PostgreSQL database"
        )
    _assert_empty_current_database(database_url)
    _assert_port_is_ours(args.port)

    project_root = _copy_test_project()
    PROJECT_MARKER.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_MARKER.write_text(str(project_root), encoding="utf-8")
    os.environ["CV_TEST_PROJECT_ROOT"] = str(project_root)
    os.environ["CV_PROVIDER"] = "deterministic"
    os.environ["CV_OBJECT_STORE"] = "local"

    previous_sigterm = signal.signal(signal.SIGTERM, _interrupt)
    try:
        return main(["web", "--no-open", "--port", str(args.port)])
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        PROJECT_MARKER.unlink(missing_ok=True)
        shutil.rmtree(project_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(run())
