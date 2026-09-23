from __future__ import annotations

from fixtures.database import alembic_head

from cv_engine.infrastructure.persistence import current_database_revision


def test_database_is_at_registered_head_schema(database_engine) -> None:
    assert current_database_revision(database_engine) == alembic_head()
