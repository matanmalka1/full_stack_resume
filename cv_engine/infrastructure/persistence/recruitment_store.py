from __future__ import annotations

from sqlalchemy import insert

from ...application.ports.transactions import WriteTransaction
from ...util import new_id
from .connection import SqlAlchemyTransactionManager
from .tables import recruitment_events


class SqlAlchemyInitialRecruitmentEventWriter:
    """The intake-owned initial event; later recruitment commands migrate separately."""

    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def insert_initial_saved_event(
        self,
        tx: WriteTransaction,
        *,
        application_id: str,
        actor_type: str,
        client: str,
        occurred_at: str,
    ) -> str:
        event_id = new_id()
        self._transactions.connection_for(tx, access="write").execute(
            insert(recruitment_events).values(
                id=event_id,
                application_id=application_id,
                event_type="status_transition",
                from_status=None,
                to_status="saved",
                reason="application created",
                actor_type=actor_type,
                client=client,
                occurred_at=occurred_at,
                payload_json={},
                created_at=occurred_at,
            )
        )
        return event_id
