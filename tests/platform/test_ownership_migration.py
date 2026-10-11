from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from cv_engine.util import new_id, utc_now

ROOT = Path(__file__).resolve().parents[2]


def _migrate(database_url: str, revision: str) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, revision) if revision == "head" else command.downgrade(config, revision)


def _legacy_application(connection, application_id: str) -> None:
    connection.execute(
        text(
            "INSERT INTO applications "
            "(id, company, target_role, current_status, notes, job_text, job_text_hash, "
            "job_normalized_hash, job_text_updated_at, created_at, updated_at) "
            "VALUES (:id, 'Legacy Co', 'Engineer', 'saved', '', 'Python', :digest, :digest, "
            ":now, :now, :now)"
        ),
        {"id": application_id, "digest": "0" * 64, "now": utc_now()},
    )


def test_ownership_migration_assigns_the_only_user_and_moves_settings(
    database_engine, database_url
) -> None:
    _migrate(database_url, "0005")
    user_id = new_id()
    application_id = new_id()
    try:
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, created_at) "
                    "VALUES (:id, 'legacy@example.com', 'test-only-hash', :now)"
                ),
                {"id": user_id, "now": utc_now()},
            )
            _legacy_application(connection, application_id)
            connection.execute(
                text(
                    "INSERT INTO app_settings "
                    "(singleton_id, edit_version, auto_generate_when_review_not_required, "
                    "default_ai_model, default_reasoning_effort, ui_density, ui_text_size, "
                    "ui_theme, updated_at) VALUES "
                    "(1, 7, true, 'gpt-5.6-terra', 'high', 'compact', 'large', 'dark', :now)"
                ),
                {"now": utc_now()},
            )

        _migrate(database_url, "head")

        with database_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT user_id FROM applications WHERE id = :id"),
                    {"id": application_id},
                ).scalar_one()
                == user_id
            )
            settings = connection.execute(
                text("SELECT user_id, edit_version, ui_theme FROM user_settings")
            ).one()
            assert tuple(settings) == (user_id, 7, "dark")
            tables = set(inspect(connection).get_table_names())
            assert "app_settings" not in tables
            assert "user_settings" in tables
    finally:
        _migrate(database_url, "head")


def test_ownership_migration_refuses_to_guess_an_existing_rows_owner(
    database_engine, database_url
) -> None:
    _migrate(database_url, "0005")
    try:
        with database_engine.begin() as connection:
            _legacy_application(connection, new_id())

        with pytest.raises(DBAPIError, match="existing rows need exactly one user"):
            _migrate(database_url, "head")

        with database_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, created_at) "
                    "VALUES (:id, 'repair@example.com', 'test-only-hash', :now)"
                ),
                {"id": new_id(), "now": utc_now()},
            )
    finally:
        _migrate(database_url, "head")
