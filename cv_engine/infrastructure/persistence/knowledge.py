from __future__ import annotations

import json
from typing import Any

from ...application.errors import (
    PreconditionFailed,
    UnknownRecord,
)
from ...application.knowledge_mutations import (
    KnowledgeMutation,
    KnowledgeMutationState,
    PrepareKnowledgeMutation,
)
from ...util import canonical_json, utc_now
from .base import SqliteRepositoryBase


class SqliteKnowledgeMutationRepository(SqliteRepositoryBase):
    """SQLite ownership for the narrow file/DB Knowledge mutation journal."""

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
            db_mutation=json.loads(row["db_mutation_json"]),
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
                "INSERT INTO knowledge_mutation_journal("
                "id, mutation_type, state, source_reference, staged_reference, old_sha256, "
                "new_sha256, db_mutation_type, db_mutation_id, db_mutation_json, "
                "recovery_strategy, prepared_at) VALUES(?, ?, 'PREPARED', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    request.mutation_id,
                    request.mutation_type,
                    request.source_reference,
                    request.staged_reference,
                    request.old_sha256,
                    request.new_sha256,
                    request.db_mutation_type,
                    request.db_mutation_id,
                    canonical_json(request.db_mutation),
                    request.recovery_strategy,
                    prepared_at or utc_now(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM knowledge_mutation_journal WHERE id=?",
                (request.mutation_id,),
            ).fetchone()
        return self._knowledge_mutation_record(row)

    def knowledge_mutation(self, mutation_id: str) -> KnowledgeMutation:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_mutation_journal WHERE id=?", (mutation_id,)
            ).fetchone()
        return self._knowledge_mutation_record(row)

    def prepared_knowledge_mutations(self) -> list[KnowledgeMutation]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_mutation_journal WHERE state='PREPARED' "
                "ORDER BY prepared_at, id"
            ).fetchall()
        return [self._knowledge_mutation_record(row) for row in rows]

    def quarantined_knowledge_mutations(self) -> list[KnowledgeMutation]:
        with self.read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_mutation_journal WHERE state='QUARANTINED' "
                "ORDER BY quarantined_at, id"
            ).fetchall()
        return [self._knowledge_mutation_record(row) for row in rows]

    def commit_knowledge_mutation(
        self, mutation_id: str, *, committed_at: str | None = None
    ) -> KnowledgeMutation:
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE knowledge_mutation_journal SET state='COMMITTED', committed_at=? "
                "WHERE id=? AND state='PREPARED'",
                (committed_at or utc_now(), mutation_id),
            )
            if cursor.rowcount != 1:
                raise PreconditionFailed("knowledge mutation is not prepared")
            row = connection.execute(
                "SELECT * FROM knowledge_mutation_journal WHERE id=?", (mutation_id,)
            ).fetchone()
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
                "UPDATE knowledge_mutation_journal SET state='QUARANTINED', "
                "quarantined_at=?, quarantine_reason=? WHERE id=? AND state='PREPARED'",
                (quarantined_at or utc_now(), reason, mutation_id),
            )
            if cursor.rowcount != 1:
                raise PreconditionFailed("knowledge mutation is not prepared")
            row = connection.execute(
                "SELECT * FROM knowledge_mutation_journal WHERE id=?", (mutation_id,)
            ).fetchone()
        return self._knowledge_mutation_record(row)
