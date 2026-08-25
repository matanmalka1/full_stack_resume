from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Engine

from alembic import command

from .connection import create_database_engine


def current_database_revision(engine: Engine) -> str | None:
    """Return the revision recorded by Alembic, or ``None`` before migration."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade_database(database_url: str) -> tuple[str | None, str | None]:
    """Upgrade one configured PostgreSQL database to the Alembic head."""
    engine = create_database_engine(database_url)
    try:
        before = current_database_revision(engine)
    finally:
        engine.dispose()

    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")

    engine = create_database_engine(database_url)
    try:
        return before, current_database_revision(engine)
    finally:
        engine.dispose()
