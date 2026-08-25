from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from ...application.errors import (
    PreconditionFailed,
    UnknownRecord,
)
from ...application.knowledge_mutations import (
    KnowledgeMutation,
    KnowledgeMutationState,
    PrepareKnowledgeMutation,
)
from ...util import utc_now
from .base import SqlAlchemyRepositoryBase
from .tables import knowledge_mutation_journal


class SqlAlchemyKnowledgeMutationRepository(SqlAlchemyRepositoryBase):
    """Persistence ownership for the narrow file/DB Knowledge mutation journal."""

    @staticmethod
    def _knowledge_mutation_record(row: Any) -> KnowledgeMutation:
        if row is None:
            raise UnknownRecord("knowledge mutation does not exist")
        return KnowledgeMutation(
            id=row["id"],
            mutation_type=row["mutation_type"],
            state=KnowledgeMutationState(row["state"]),
            source_reference=row["source_reference"],
            staged_reference=row["staged_reference"],
            old_sha256=row["old_sha256"],
            new_sha256=row["new_sha256"],
            db_mutation_type=row["db_mutation_type"],
            db_mutation_id=row["db_mutation_id"],
            db_mutation=row["db_mutation_json"],
            recovery_strategy=row["recovery_strategy"],
            prepared_at=row["prepared_at"],
            committed_at=row["committed_at"],
            quarantined_at=row["quarantined_at"],
            quarantine_reason=row["quarantine_reason"],
        )

    def prepare_knowledge_mutation(
        self, request: PrepareKnowledgeMutation, *, prepared_at: str | None = None
    ) -> KnowledgeMutation:
        with self.transaction() as connection:
            connection.execute(
                insert(knowledge_mutation_journal).values(
                    id=request.mutation_id,
                    mutation_type=request.mutation_type,
                    state="PREPARED",
                    source_reference=request.source_reference,
                    staged_reference=request.staged_reference,
                    old_sha256=request.old_sha256,
                    new_sha256=request.new_sha256,
                    db_mutation_type=request.db_mutation_type,
                    db_mutation_id=request.db_mutation_id,
                    db_mutation_json=request.db_mutation,
                    recovery_strategy=request.recovery_strategy,
                    prepared_at=prepared_at or utc_now(),
                )
            )
            row = (
                connection.execute(
                    select(knowledge_mutation_journal).where(
                        knowledge_mutation_journal.c.id == request.mutation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        return self._knowledge_mutation_record(row)

    def knowledge_mutation(self, mutation_id: str) -> KnowledgeMutation:
        with self.read_connection() as connection:
            row = (
                connection.execute(
                    select(knowledge_mutation_journal).where(
                        knowledge_mutation_journal.c.id == mutation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        return self._knowledge_mutation_record(row)

    def prepared_knowledge_mutations(self) -> list[KnowledgeMutation]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(knowledge_mutation_journal)
                    .where(knowledge_mutation_journal.c.state == "PREPARED")
                    .order_by(
                        knowledge_mutation_journal.c.prepared_at,
                        knowledge_mutation_journal.c.id,
                    )
                )
                .mappings()
                .all()
            )
        return [self._knowledge_mutation_record(row) for row in rows]

    def quarantined_knowledge_mutations(self) -> list[KnowledgeMutation]:
        with self.read_connection() as connection:
            rows = (
                connection.execute(
                    select(knowledge_mutation_journal)
                    .where(knowledge_mutation_journal.c.state == "QUARANTINED")
                    .order_by(
                        knowledge_mutation_journal.c.quarantined_at,
                        knowledge_mutation_journal.c.id,
                    )
                )
                .mappings()
                .all()
            )
        return [self._knowledge_mutation_record(row) for row in rows]

    def commit_knowledge_mutation(
        self, mutation_id: str, *, committed_at: str | None = None
    ) -> KnowledgeMutation:
        with self.transaction() as connection:
            cursor = connection.execute(
                update(knowledge_mutation_journal)
                .where(
                    knowledge_mutation_journal.c.id == mutation_id,
                    knowledge_mutation_journal.c.state == "PREPARED",
                )
                .values(state="COMMITTED", committed_at=committed_at or utc_now())
            )
            if cursor.rowcount != 1:
                raise PreconditionFailed("knowledge mutation is not prepared")
            row = (
                connection.execute(
                    select(knowledge_mutation_journal).where(
                        knowledge_mutation_journal.c.id == mutation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        return self._knowledge_mutation_record(row)

    def quarantine_knowledge_mutation(
        self,
        mutation_id: str,
        reason: str,
        *,
        quarantined_at: str | None = None,
    ) -> KnowledgeMutation:
        if not reason.strip():
            raise PreconditionFailed("knowledge mutation quarantine requires a reason")
        with self.transaction() as connection:
            cursor = connection.execute(
                update(knowledge_mutation_journal)
                .where(
                    knowledge_mutation_journal.c.id == mutation_id,
                    knowledge_mutation_journal.c.state == "PREPARED",
                )
                .values(
                    state="QUARANTINED",
                    quarantined_at=quarantined_at or utc_now(),
                    quarantine_reason=reason,
                )
            )
            if cursor.rowcount != 1:
                raise PreconditionFailed("knowledge mutation is not prepared")
            row = (
                connection.execute(
                    select(knowledge_mutation_journal).where(
                        knowledge_mutation_journal.c.id == mutation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        return self._knowledge_mutation_record(row)
