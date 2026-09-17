"""Legacy Phase-8 Operation reads used only by application projections."""

from __future__ import annotations

from sqlalchemy import case, select

from ...application.operations import (
    MATCHING_CONTEXT_OPERATION_TYPES,
    OperationView,
    as_operation_view,
)
from .base import SqlAlchemyRepositoryBase
from .operation_sql import _operation_record, _outputs
from .tables import operations


class SqlAlchemyOperationProjection(SqlAlchemyRepositoryBase):
    def active_operation(self, application_id: str) -> OperationView | None:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(operations)
                    .where(
                        operations.c.application_id == application_id,
                        operations.c.status.in_(("queued", "running")),
                    )
                    .order_by(
                        case((operations.c.status == "running", 0), else_=1),
                        operations.c.created_at,
                        operations.c.id,
                    )
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return as_operation_view(_operation_record(row, _outputs(connection, row["id"])))

    def has_active_matching_context_operation(self, application_id: str) -> bool:
        with self.read_connection() as connection:
            return (
                connection.execute(
                    select(operations.c.id)
                    .where(
                        operations.c.application_id == application_id,
                        operations.c.status.in_(("queued", "running")),
                        operations.c.operation_type.in_(
                            tuple(kind.value for kind in MATCHING_CONTEXT_OPERATION_TYPES)
                        ),
                    )
                    .limit(1)
                ).scalar_one_or_none()
                is not None
            )

    def latest_operation(self, application_id: str) -> OperationView | None:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(operations)
                    .where(operations.c.application_id == application_id)
                    .order_by(operations.c.created_at.desc(), operations.c.id.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return as_operation_view(_operation_record(row, _outputs(connection, row["id"])))
