"""Stateless transaction-token persistence for the Knowledge lifecycle."""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from ...application.errors import PreconditionFailed, StateConflict, UnknownRecord
from ...application.knowledge_mutations import (
    KnowledgeMutation,
    KnowledgeMutationState,
    PrepareKnowledgeMutation,
)
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...domain.contracts.drafts import WorkingDraft
from ...domain.contracts.selection import SelectionManifest, SelectionPlan
from ...util import canonical_json, new_id, sha256_text, utc_now
from .analysis_sql import _analysis_record, _create_selection_plan, _selection_plan_record
from .connection import SqlAlchemyTransactionManager
from .drafts_sql import _active_working_draft
from .tables import fact_events, job_analyses, knowledge_mutation_journal, selection_plans


class SqlAlchemyKnowledgeLifecycleRepository:
    """Own fact events and mutation-journal state behind explicit tokens."""

    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    @staticmethod
    def _record(row: Any) -> KnowledgeMutation:
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

    def prepare_mutation(
        self,
        tx: WriteTransaction,
        request: PrepareKnowledgeMutation,
        *,
        prepared_at: str | None = None,
    ) -> KnowledgeMutation:
        connection = self._transactions.connection_for(tx, access="write")
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
        return self.mutation(tx, request.mutation_id)

    def mutation(self, tx: ReadTransaction, mutation_id: str) -> KnowledgeMutation:
        row = (
            self._transactions.connection_for(tx)
            .execute(
                select(knowledge_mutation_journal).where(
                    knowledge_mutation_journal.c.id == mutation_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return self._record(row)

    def prepared_mutations(self, tx: ReadTransaction) -> list[KnowledgeMutation]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
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
        return [self._record(row) for row in rows]

    def quarantined_mutations(self, tx: ReadTransaction) -> list[KnowledgeMutation]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
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
        return [self._record(row) for row in rows]

    def commit_mutation(
        self,
        tx: WriteTransaction,
        mutation_id: str,
        *,
        committed_at: str | None = None,
    ) -> KnowledgeMutation:
        connection = self._transactions.connection_for(tx, access="write")
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
        return self.mutation(tx, mutation_id)

    def quarantine_mutation(
        self,
        tx: WriteTransaction,
        mutation_id: str,
        reason: str,
        *,
        quarantined_at: str | None = None,
    ) -> KnowledgeMutation:
        if not reason.strip():
            raise PreconditionFailed("knowledge mutation quarantine requires a reason")
        connection = self._transactions.connection_for(tx, access="write")
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
        return self.mutation(tx, mutation_id)

    def record_fact_event(self, tx: WriteTransaction, **event: Any) -> str:
        connection = self._transactions.connection_for(tx, access="write")
        event_id = event.get("event_id") or new_id()
        values = {
            "id": event_id,
            "fact_id": event["fact_id"],
            "source_file": event["source_file"],
            "event_type": event["event_type"],
            "from_status": event["from_status"],
            "to_status": event["to_status"],
            "application_id": event.get("application_id"),
            "claim_id": event.get("claim_id"),
            "reason": event.get("reason", ""),
            "fact_json": event["fact"],
            "fact_hash": sha256_text(canonical_json(event["fact"])),
            "facts_version": event["facts_version"],
            "lifecycle_version": event["lifecycle_version"],
            "created_at": event.get("created_at") or utc_now(),
        }
        visible = [column for column in fact_events.c if column.name != "seq"]
        existing = (
            connection.execute(select(*visible).where(fact_events.c.id == event_id))
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if dict(existing) != values:
                raise StateConflict("fact event identity already has different content")
            return event_id
        connection.execute(insert(fact_events).values(**values))
        return event_id

    @staticmethod
    def _event_record(row: Any) -> dict[str, Any]:
        record = dict(row)
        record["fact_json"] = canonical_json(record["fact_json"])
        return record

    def fact_event(self, tx: ReadTransaction, event_id: str) -> dict[str, Any] | None:
        visible = [column for column in fact_events.c if column.name != "seq"]
        row = (
            self._transactions.connection_for(tx)
            .execute(select(*visible).where(fact_events.c.id == event_id))
            .mappings()
            .one_or_none()
        )
        return None if row is None else self._event_record(row)

    def fact_events(self, tx: ReadTransaction, fact_id: str | None = None) -> list[dict[str, Any]]:
        visible = [column for column in fact_events.c if column.name != "seq"]
        statement = select(*visible)
        if fact_id is not None:
            statement = statement.where(fact_events.c.fact_id == fact_id)
        rows = self._transactions.connection_for(tx).execute(
            statement.order_by(fact_events.c.created_at, fact_events.c.seq)
        )
        return [self._event_record(row) for row in rows.mappings()]

    def latest_fact_statuses(self, tx: ReadTransaction) -> dict[str, str]:
        rows = (
            self._transactions.connection_for(tx)
            .execute(
                select(fact_events.c.fact_id, fact_events.c.to_status)
                .where(
                    fact_events.c.event_type.in_(("fact_created", "fact_promoted", "fact_deleted"))
                )
                .order_by(fact_events.c.created_at, fact_events.c.seq)
            )
            .mappings()
            .all()
        )
        return {row["fact_id"]: row["to_status"] for row in rows}

    def get_analysis(self, tx: ReadTransaction, analysis_id: str) -> dict[str, Any]:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(job_analyses).where(job_analyses.c.id == analysis_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"no job analysis {analysis_id}")
        return _analysis_record(row)

    def active_working_draft(self, tx: ReadTransaction, application_id: str) -> WorkingDraft:
        return _active_working_draft(self._transactions.connection_for(tx), application_id)

    def create_selection_plan(
        self,
        tx: WriteTransaction,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        *,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        plan_id: str | None = None,
        created_at: str | None = None,
    ) -> SelectionPlan:
        connection = self._transactions.connection_for(tx, access="write")
        if plan_id is not None:
            existing_row = (
                connection.execute(select(selection_plans).where(selection_plans.c.id == plan_id))
                .mappings()
                .one_or_none()
            )
            if existing_row is not None:
                existing = _selection_plan_record(existing_row)
                expected = {
                    "application_id": application_id,
                    "job_analysis_id": job_analysis_id,
                    "plan": plan,
                    "candidate_context_version": candidate_context_version,
                    "candidate_context_hash": candidate_context_hash,
                    "profile_version": profile_version,
                    "selection_policy_version": selection_policy_version,
                    "track_emphasis_dependencies": track_emphasis_dependencies,
                    "created_at": created_at,
                }
                actual = {
                    "application_id": existing.application_id,
                    "job_analysis_id": existing.job_analysis_id,
                    "plan": existing.plan,
                    "candidate_context_version": existing.candidate_context_version,
                    "candidate_context_hash": existing.candidate_context_hash,
                    "profile_version": existing.profile_version,
                    "selection_policy_version": existing.selection_policy_version,
                    "track_emphasis_dependencies": existing.track_emphasis_dependencies,
                    "created_at": existing.created_at,
                }
                if actual != expected:
                    raise StateConflict("selection plan identity already has different content")
                return existing
        return _create_selection_plan(
            connection,
            application_id,
            job_analysis_id,
            plan,
            candidate_context_version=candidate_context_version,
            candidate_context_hash=candidate_context_hash,
            profile_version=profile_version,
            selection_policy_version=selection_policy_version,
            track_emphasis_dependencies=track_emphasis_dependencies,
            plan_id=plan_id,
            created_at=created_at,
        )

    def selection_plan(self, tx: ReadTransaction, selection_plan_id: str) -> SelectionPlan:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(selection_plans).where(selection_plans.c.id == selection_plan_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"no selection plan {selection_plan_id}")
        return _selection_plan_record(row)
