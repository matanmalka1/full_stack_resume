from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from ...application.errors import LineageBroken, StateConflict, UnknownRecord
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...util import new_id
from .base import json_text_record
from .connection import SqlAlchemyTransactionManager
from .tables import applications, recruitment_events, submissions


class SqlAlchemyRecruitmentRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def application(self, tx: ReadTransaction, application_id: str) -> dict[str, Any]:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(applications).where(applications.c.id == application_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        return dict(row)

    def set_deleted(self, tx: WriteTransaction, application_id: str, deleted_at: str) -> None:
        result = self._transactions.connection_for(tx, access="write").execute(
            update(applications)
            .where(
                applications.c.id == application_id,
                applications.c.deleted_at.is_(None),
            )
            .values(deleted_at=deleted_at, updated_at=deleted_at)
        )
        if result.rowcount != 1:
            raise StateConflict(f"application is deleted: {application_id}")

    def event(self, tx: ReadTransaction, event_id: str) -> dict[str, Any]:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(recruitment_events).where(recruitment_events.c.id == event_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(event_id)
        return json_text_record(row, "payload_json")

    def insert_event(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        expected_current_status: str,
        target_status: str,
        event_type: str,
        reason: str,
        actor_type: str,
        client: str,
        occurred_at: str,
        terminal_outcome: str | None,
        corrects_event_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> str:
        connection = self._transactions.connection_for(tx, access="write")
        expected = expected_current_status
        row = (
            connection.execute(
                select(applications.c.current_status)
                .where(applications.c.id == application_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        if row["current_status"] != expected:
            raise StateConflict(
                f"application status changed before commit: expected {expected}, found {row['current_status']}"
            )
        corrected_id = corrects_event_id
        if corrected_id is not None:
            owner = connection.execute(
                select(recruitment_events.c.application_id).where(
                    recruitment_events.c.id == corrected_id
                )
            ).scalar_one_or_none()
            if owner is None:
                raise UnknownRecord(corrected_id)
            if owner != application_id:
                raise LineageBroken("a correction cannot reference another application's event")
        identity = event_id or new_id()
        connection.execute(
            update(applications)
            .where(applications.c.id == application_id)
            .values(
                current_status=target_status,
                terminal_outcome=terminal_outcome,
                updated_at=occurred_at,
            )
        )
        connection.execute(
            insert(recruitment_events).values(
                id=identity,
                application_id=application_id,
                event_type=event_type,
                from_status=expected,
                to_status=target_status,
                corrects_event_id=corrected_id,
                reason=reason,
                actor_type=actor_type,
                client=client,
                occurred_at=occurred_at,
                payload_json=payload or {},
                created_at=occurred_at,
            )
        )
        return identity

    def insert_next_action(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        next_action: str | None,
        next_action_date: str | None,
        actor_type: str,
        client: str,
        occurred_at: str,
    ) -> str:
        connection = self._transactions.connection_for(tx, access="write")
        row = (
            connection.execute(
                select(applications.c.current_status)
                .where(applications.c.id == application_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(application_id)
        event_id = new_id()
        connection.execute(
            update(applications)
            .where(applications.c.id == application_id)
            .values(
                next_action=next_action, next_action_date=next_action_date, updated_at=occurred_at
            )
        )
        connection.execute(
            insert(recruitment_events).values(
                id=event_id,
                application_id=application_id,
                event_type="next_action",
                from_status=row["current_status"],
                to_status=row["current_status"],
                reason="",
                actor_type=actor_type,
                client=client,
                occurred_at=occurred_at,
                payload_json={"next_action": next_action, "next_action_date": next_action_date},
                created_at=occurred_at,
            )
        )
        return event_id

    def insert_submission(
        self,
        tx: WriteTransaction,
        submission_id: str,
        application_id: str,
        submission_type: str,
        approved_revision_id: str | None,
        artifact_version_id: str | None,
        submitted_at: str,
        metadata: dict[str, Any],
    ) -> None:
        self._transactions.connection_for(tx, access="write").execute(
            insert(submissions).values(
                id=submission_id,
                application_id=application_id,
                submission_type=submission_type,
                approved_revision_id=approved_revision_id,
                artifact_version_id=artifact_version_id,
                submitted_at=submitted_at,
                metadata_json=metadata,
            )
        )
