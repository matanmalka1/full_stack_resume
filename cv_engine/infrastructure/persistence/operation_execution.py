"""Runner-owned Operation execution persistence."""

from __future__ import annotations

from sqlalchemy import exists, insert, null, select, update
from sqlalchemy.exc import DBAPIError

from ...application.errors import StateConflict, UnknownRecord
from ...application.operations import (
    ClaimReviewReason,
    FailureReason,
    OperationFailureCode,
    OperationPhase,
    OperationStatus,
    PersistedOperation,
)
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...util import new_id, utc_now
from .analysis_sql import _lock_application
from .connection import SqlAlchemyTransactionManager
from .operation_sql import _operation_record
from .tables import operation_outputs, operations

#: The partial unique indexes that refuse a second running Operation (architecture.md
#: §10). A claim that violates one of these lost to work already running and moves on;
#: any other unique violation is a real error and is raised.
CLAIM_GUARDS = frozenset({"uq_operations_running_application", "uq_operations_running_render"})


def _lost_claim(error: DBAPIError) -> bool:
    """A claim another claimant won: a serialization failure, or a claim-guard violation.

    Under REPEATABLE READ, SKIP LOCKED only skips a row locked now; a row a rival
    claimed and committed after this snapshot is refused with 40001. A guard
    violation is told apart from every other 23505 by the index it names.
    """
    sqlstate = getattr(error.orig, "sqlstate", None)
    if sqlstate == "40001":
        return True
    diag = getattr(error.orig, "diag", None)
    return sqlstate == "23505" and getattr(diag, "constraint_name", None) in CLAIM_GUARDS


class SqlAlchemyOperationExecutionStore:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None:
        _lock_application(self._transactions.connection_for(tx, access="write"), application_id)

    def claim_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        now: str | None = None,
    ) -> PersistedOperation | None:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        try:
            # One savepoint per candidate: a lost claim rolls back to it and leaves the
            # caller's transaction usable for the next candidate.
            with connection.begin_nested():
                row = (
                    connection.execute(
                        select(operations.c.id, operations.c.status)
                        .where(operations.c.id == operation_id)
                        .with_for_update(skip_locked=True)
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None or row["status"] != OperationStatus.QUEUED.value:
                    changed = 0
                else:
                    # The claim guards decide here, atomically: the unique check is not
                    # snapshot-bound, so a rival's committed running row is seen, and an
                    # uncommitted one is waited for.
                    changed = connection.execute(
                        update(operations)
                        .where(operations.c.id == operation_id, operations.c.status == "queued")
                        .values(
                            status="running",
                            phase=OperationPhase.EXECUTING.value,
                            message="",
                            started_at=timestamp,
                            lease_owner=runner_id,
                        )
                    ).rowcount
        except DBAPIError as error:
            if not _lost_claim(error):
                raise
            return None
        if row is None:
            # A row locked by a concurrent claimant is a lost claim; only an actually
            # unknown identifier is an error.
            known = connection.execute(
                select(operations.c.id).where(operations.c.id == operation_id)
            ).scalar_one_or_none()
            if known is None:
                raise UnknownRecord("operation does not exist")
            return None
        if changed != 1:
            return None
        current = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one()
        )
        return _operation_record(current, connection)

    def claim_next_operation(
        self,
        tx: WriteTransaction,
        *,
        runner_id: str,
        now: str | None = None,
    ) -> PersistedOperation | None:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        running = operations.alias("running")
        # Skipping what would only lose to running work is an optimisation that keeps
        # a busy Application from being retried on every poll; the claim guards in
        # `claim_operation` are what make the rule hold.
        candidates = (
            connection.execute(
                select(operations.c.id)
                .where(
                    operations.c.status == "queued",
                    ~exists().where(
                        running.c.status == "running",
                        running.c.application_id == operations.c.application_id,
                    ),
                    ~(
                        (operations.c.operation_type == "render_document")
                        & exists().where(
                            running.c.status == "running",
                            running.c.operation_type == "render_document",
                        )
                    ),
                )
                .order_by(operations.c.created_at, operations.c.id)
            )
            .scalars()
            .all()
        )
        for operation_id in candidates:
            claimed = self.claim_operation(tx, operation_id, runner_id=runner_id, now=timestamp)
            if claimed is not None:
                return claimed
        return None

    def interrupt_claims_from_previous_runners(
        self, tx: WriteTransaction, *, now: str | None = None
    ) -> list[str]:
        """Interrupt every running Operation, for a fresh worker's one-time sweep.

        Called once, before this worker has claimed anything of its own. Only
        one worker runs at a time (`worker_exclusivity`), so any running row
        belongs to a worker that no longer exists. An external call it made is
        never resumed.
        """
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        identifiers = list(
            connection.execute(
                select(operations.c.id)
                .where(operations.c.status == OperationStatus.RUNNING.value)
                .order_by(operations.c.created_at, operations.c.id)
            ).scalars()
        )
        for identifier in identifiers:
            connection.execute(
                update(operations)
                .where(
                    operations.c.id == identifier,
                    operations.c.status == OperationStatus.RUNNING.value,
                )
                .values(
                    status="interrupted",
                    phase="completed",
                    message="Interrupted by a fresh worker startup.",
                    finished_at=timestamp,
                    lease_owner=None,
                )
            )
        return identifiers

    def operation(self, tx: ReadTransaction, operation_id: str) -> PersistedOperation:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(row, connection)

    def cancellation_requested(self, tx: ReadTransaction, operation_id: str) -> bool:
        connection = self._transactions.connection_for(tx)
        row = (
            connection.execute(
                select(operations.c.cancellation_requested_at).where(
                    operations.c.id == operation_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord("operation does not exist")
        return row["cancellation_requested_at"] is not None

    def execution_still_owned(
        self, tx: ReadTransaction, operation_id: str, *, runner_id: str
    ) -> bool:
        """The Operation is still running, held by `runner_id`, with no cancellation asked.

        What must hold before this runner starts another provider call for it.
        """
        connection = self._transactions.connection_for(tx)
        owned = connection.execute(
            select(operations.c.id).where(
                operations.c.id == operation_id,
                operations.c.status == OperationStatus.RUNNING.value,
                operations.c.lease_owner == runner_id,
                operations.c.cancellation_requested_at.is_(None),
            )
        ).scalar_one_or_none()
        return owned is not None

    def record_operation_output(
        self,
        tx: WriteTransaction,
        operation_id: str,
        output_type: str,
        output_id: str,
    ) -> str:
        """Record what an activation produced, in the activation's own transaction.

        Only a running Operation with no cancellation asked may record one, so an
        output exists exactly when the Operation succeeded with it.
        """
        identifier = new_id()
        connection = self._transactions.connection_for(tx, access="write")
        operation = (
            connection.execute(
                select(operations.c.status, operations.c.cancellation_requested_at).where(
                    operations.c.id == operation_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if operation is None:
            raise UnknownRecord("operation does not exist")
        if (
            operation["status"] != OperationStatus.RUNNING.value
            or operation["cancellation_requested_at"] is not None
        ):
            raise StateConflict("operation output cannot be recorded")
        connection.execute(
            insert(operation_outputs).values(
                id=identifier,
                operation_id=operation_id,
                output_type=output_type,
                output_id=output_id,
                created_at=utc_now(),
            )
        )
        return identifier

    def complete_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        *,
        runner_id: str,
        withheld_claims: ClaimReviewReason | None = None,
        now: str | None = None,
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        row = (
            connection.execute(
                select(operations).where(
                    operations.c.id == operation_id,
                    operations.c.status == "running",
                    operations.c.lease_owner == runner_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise StateConflict("operation lease is not owned by this runner")
        if row["cancellation_requested_at"] is not None:
            status = OperationStatus.CANCELLED.value
            failure_code = OperationFailureCode.CANCELLED_BEFORE_ACTIVATION.value
            message = "Cancelled before output activation."
            # Nothing activated, so nothing was withheld from anything written.
            withheld_claims = None
        else:
            status = OperationStatus.SUCCEEDED.value
            failure_code = None
            message = ""
        connection.execute(
            update(operations)
            .where(
                operations.c.id == operation_id,
                operations.c.status == "running",
                operations.c.lease_owner == runner_id,
            )
            .values(
                status=status,
                phase="completed",
                message=message,
                finished_at=timestamp,
                failure_code=failure_code,
                safe_failure_detail=message or None,
                # SQL NULL for "none withheld", as `fail_operation` does for its reason.
                withheld_claims=(
                    null() if withheld_claims is None else withheld_claims.model_dump(mode="json")
                ),
                lease_owner=None,
            )
        )
        current = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(current, connection)

    def fail_operation(
        self,
        tx: WriteTransaction,
        operation_id: str,
        code: OperationFailureCode,
        safe_detail: str,
        *,
        runner_id: str,
        technical_log_reference: str | None = None,
        reason: FailureReason | None = None,
        now: str | None = None,
    ) -> PersistedOperation:
        timestamp = now or utc_now()
        connection = self._transactions.connection_for(tx, access="write")
        changed = connection.execute(
            update(operations)
            .where(
                operations.c.id == operation_id,
                operations.c.status == "running",
                operations.c.lease_owner == runner_id,
            )
            .values(
                status="failed",
                phase="completed",
                message="",
                finished_at=timestamp,
                failure_code=code.value,
                safe_failure_detail=safe_detail,
                # SQL NULL, not the JSON `null` a bare None becomes in a JSONB column:
                # "no reason recorded" is the column's absence, and the shape check
                # refuses a JSON scalar.
                failure_reason=null() if reason is None else reason.model_dump(mode="json"),
                technical_log_reference=technical_log_reference,
                lease_owner=None,
            )
        ).rowcount
        if changed != 1:
            raise StateConflict("operation lease is not owned by this runner")
        current = (
            connection.execute(select(operations).where(operations.c.id == operation_id))
            .mappings()
            .one_or_none()
        )
        return _operation_record(current, connection)
