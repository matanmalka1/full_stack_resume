from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from ...application.errors import UnknownRecord
from .base import SqlAlchemyRepositoryBase
from .tables import applications


class SqlAlchemyApplicationRepository(SqlAlchemyRepositoryBase):
    def get_application(self, application_id: str) -> dict[str, Any]:
        with self.read_connection() as connection:
            row = (
                connection.execute(select(applications).where(applications.c.id == application_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def list_applications(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        with self.read_connection() as connection:
            query = select(applications).order_by(applications.c.created_at, applications.c.id)
            if not include_deleted:
                query = query.where(applications.c.deleted_at.is_(None))
            rows = connection.execute(query).mappings()
            return [dict(row) for row in rows]

    def set_application_deleted(self, application_id: str, deleted_at: str) -> None:
        with self.transaction() as connection:
            result = connection.execute(
                update(applications)
                .where(applications.c.id == application_id)
                .values(deleted_at=deleted_at, updated_at=deleted_at)
            )
            if result.rowcount != 1:
                raise UnknownRecord(application_id)
