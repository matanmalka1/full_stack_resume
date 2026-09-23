from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError

from cv_engine.infrastructure.persistence import (
    SqlAlchemyTransactionManager,
    create_database_engine,
    current_database_revision,
)
from cv_engine.infrastructure.persistence.analysis_plans import SqlAlchemyAnalysisPlanRepository
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.infrastructure.persistence.audit_log import SqlAlchemyAuditLog
from cv_engine.infrastructure.persistence.draft_lifecycle import (
    SqlAlchemyDraftLifecycleRepository,
)
from cv_engine.infrastructure.persistence.job_snapshots import SqlAlchemyJobSnapshotStore
from cv_engine.infrastructure.persistence.tables import metadata
from cv_engine.infrastructure.persistence.validation_store import SqlAlchemyValidationRepository
from cv_engine.runtime.config import resolve_config

SOURCE_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_SUFFIX = "_test"


def _isolated_database_url(configured: str) -> str:
    """Derive the suite's database from the configured one, never reusing it."""
    url = make_url(configured)
    override = os.environ.get("CV_TEST_DATABASE_URL")
    if override:
        candidate = make_url(override)
        if (candidate.host, candidate.port, candidate.database) == (
            url.host,
            url.port,
            url.database,
        ):
            raise RuntimeError(
                "CV_TEST_DATABASE_URL names the configured runtime database "
                f"({url.database!r}); the suite truncates every table, so it "
                "must point at a separate database"
            )
        return candidate.render_as_string(hide_password=False)
    name = url.database or ""
    if not name.endswith(TEST_DATABASE_SUFFIX):
        name = f"{name}{TEST_DATABASE_SUFFIX}"
    return url.set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def database_url() -> str:
    return _isolated_database_url(str(resolve_config(env=os.environ).get("database_url")))


def alembic_head() -> str:
    """Read the single registered head from Alembic rather than pinning it."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    heads = ScriptDirectory.from_config(Config(str(SOURCE_ROOT / "alembic.ini"))).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Alembic must have exactly one head, found {heads}")
    return heads[0]


@pytest.fixture(scope="session")
def database_engine(database_url: str) -> Iterator[Engine]:
    engine = create_database_engine(database_url)
    head = alembic_head()
    try:
        revision = current_database_revision(engine)
    except OperationalError as error:
        engine.dispose()
        raise RuntimeError(
            f"the isolated test database {engine.url.database!r} is unreachable; "
            "create it once with "
            f"'docker compose exec postgres createdb -U cv {engine.url.database}' "
            "and migrate it with "
            f"'CV_DATABASE_URL={engine.url.render_as_string(hide_password=False)} "
            "./.venv/bin/alembic upgrade head'"
        ) from error
    if revision != head:
        engine.dispose()
        raise RuntimeError(
            f"test database {engine.url.database!r} is not at Alembic revision {head}; run "
            f"'CV_DATABASE_URL={engine.url.render_as_string(hide_password=False)} "
            "./.venv/bin/alembic upgrade head' first"
        )
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def isolated_database(database_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test an empty database and no ambient paid provider."""
    table_names = ", ".join(f'"{name}"' for name in metadata.tables)
    with database_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    monkeypatch.setenv(
        "CV_DATABASE_URL",
        database_engine.url.render_as_string(hide_password=False),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def transaction_manager(database_engine: Engine) -> SqlAlchemyTransactionManager:
    return SqlAlchemyTransactionManager(database_engine)


@pytest.fixture
def application_store(transaction_manager):
    return SqlAlchemyApplicationStore(transaction_manager)


@pytest.fixture
def job_snapshot_store(transaction_manager):
    return SqlAlchemyJobSnapshotStore(transaction_manager)


@pytest.fixture
def analysis_plan_store(transaction_manager):
    return SqlAlchemyAnalysisPlanRepository(transaction_manager)


@pytest.fixture
def draft_lifecycle_store(transaction_manager):
    return SqlAlchemyDraftLifecycleRepository(transaction_manager)


@pytest.fixture
def artifact_catalog(transaction_manager):
    return SqlAlchemyArtifactCatalog(transaction_manager)


@pytest.fixture
def validation_store(transaction_manager):
    return SqlAlchemyValidationRepository(transaction_manager)


@pytest.fixture
def audit_log(transaction_manager):
    return SqlAlchemyAuditLog(transaction_manager)


@pytest.fixture
def application_projection_reader(transaction_manager):
    return SqlAlchemyApplicationProjectionReader(transaction_manager)
