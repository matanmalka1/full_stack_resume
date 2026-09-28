from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

from ...application.errors import StateConflict, UnknownRecord
from ...application.operations import MATCHING_CONTEXT_OPERATION_TYPES
from ...domain.contracts.analysis import JobAnalysis
from ...util import new_id, utc_now
from .tables import applications, job_analyses, job_snapshots, operations


def _lock_application(connection: Connection, application_id: str) -> None:
    """Serialize every analysis, document-creation and activation write for one Application.

    Under REPEATABLE READ, callers take the lock before source reads so their
    snapshot is established under the lock. Analysis versions are allocated only
    after locking; evidence registration repeats its deduplication lookup under the
    same lock. Operation activation takes it as its first statement.
    """
    connection.execute(
        select(applications.c.id).where(applications.c.id == application_id).with_for_update()
    ).one_or_none()


def _active_analysis_id(connection: Connection, application_id: str) -> str | None:
    """The newest analysis of the active JobSnapshot, the one a decision form shows."""
    active_snapshot_id = connection.execute(
        select(job_snapshots.c.id)
        .where(job_snapshots.c.application_id == application_id)
        .order_by(job_snapshots.c.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    return connection.execute(
        select(job_analyses.c.id)
        .where(
            job_analyses.c.application_id == application_id,
            job_analyses.c.job_snapshot_id == active_snapshot_id,
        )
        .order_by(job_analyses.c.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def _refuse_moved_analysis(
    connection: Connection, application_id: str, expected_analysis_id: str | None
) -> None:
    """CAS the analysis a decision was made against, while the Application is locked.

    A fresh analyze passes no expected analysis and is unaffected. An explicit
    decision passes the analysis it observed; checking it in the transaction that
    inserts the replacement prevents a stale browser tab from reviving an older one.
    """
    if expected_analysis_id is None:
        return
    active_analysis_id = _active_analysis_id(connection, application_id)
    if active_analysis_id != expected_analysis_id:
        raise StateConflict(
            "the active JobAnalysis moved since this decision was made "
            "(expected_analysis_id): "
            f"expected {expected_analysis_id}, found {active_analysis_id or 'none'}"
        )


def _refuse_matching_context_operation(connection: Connection, application_id: str) -> None:
    competing = (
        connection.execute(
            select(operations.c.id, operations.c.operation_type)
            .where(
                operations.c.application_id == application_id,
                operations.c.status.in_(("queued", "running")),
                operations.c.operation_type.in_(
                    tuple(kind.value for kind in MATCHING_CONTEXT_OPERATION_TYPES)
                ),
            )
            .order_by(operations.c.created_at, operations.c.id)
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    if competing is not None:
        raise StateConflict(
            "matching configuration cannot change while a context Operation is active: "
            f"{competing['operation_type']} {competing['id']}"
        )


def _analysis_record(row: Any) -> dict[str, Any]:
    record = dict(row)
    document = record.pop("structured_json")
    version = document.get("analysis_version") if isinstance(document, dict) else None
    if version != "3.0":
        # Said out loud rather than adapted. A reader that filled in the
        # fields a 2.0 document lacks would be inventing an analysis nobody
        # produced, and one that kept both shapes alive would leave two
        # models in the one place this stage exists to reduce to one.
        raise UnknownRecord(
            f"job analysis {record.get('id')} is stored as analysis_version "
            f"{version!r}; only 3.0 can be read"
        )
    record["analysis"] = JobAnalysis.model_validate(document)
    return record


def _save_analysis(
    connection: Connection,
    application_id: str,
    snapshot_id: str,
    analysis: JobAnalysis,
    *,
    provider: str,
    model: str,
    expected_analysis_id: str | None = None,
    refuse_matching_context_operation: bool = False,
) -> str:
    """Write one immutable JobAnalysis; its ID is its identity (decision 2).

    The CV document is not written here. Creating it with the analysis's
    deterministic selection is the application's decision, taken in the same
    transaction under the same Application lock.
    """
    analysis_id = new_id()
    now = utc_now()
    _lock_application(connection, application_id)
    _refuse_moved_analysis(connection, application_id, expected_analysis_id)
    if refuse_matching_context_operation:
        _refuse_matching_context_operation(connection, application_id)
    # Allocated under the lock. Read before it, the highest version is
    # whatever the snapshot happened to see, and the insert collides on
    # the unique constraint instead of taking the next number.
    version = connection.execute(
        select(
            (func.coalesce(func.max(job_analyses.c.version_number), 0) + 1).label("version")
        ).where(job_analyses.c.application_id == application_id)
    ).scalar_one()
    connection.execute(
        insert(job_analyses).values(
            id=analysis_id,
            application_id=application_id,
            job_snapshot_id=snapshot_id,
            version_number=version,
            structured_json=analysis.model_dump(mode="json"),
            provider=provider,
            model=model,
            created_at=now,
        )
    )
    connection.execute(
        update(applications)
        .where(applications.c.id == application_id)
        # Classification only. Fit is projected from the requirements where it is
        # read (`analysis/projection.py`), never copied onto the row.
        .values(
            language=analysis.language,
            track=analysis.track.value,
            profile=analysis.profile.value,
            emphasis=analysis.emphasis.value,
            updated_at=now,
        )
    )
    return analysis_id
