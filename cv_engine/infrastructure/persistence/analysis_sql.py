from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

from ...application.errors import (
    LineageBroken,
    StateConflict,
    UnknownRecord,
)
from ...application.operations import MATCHING_CONTEXT_OPERATION_TYPES
from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.selection import (
    SelectionManifest,
    SelectionPlan,
)
from ...util import new_id, utc_now
from .tables import applications, job_analyses, job_snapshots, operations, selection_plans


def _lock_application(connection: Connection, application_id: str) -> None:
    """Serialize every plan write for one Application.

    Under REPEATABLE READ, callers take the lock before source reads so their
    snapshot is established under the lock. Plan writers allocate versions
    only after locking; evidence registration repeats its deduplication lookup
    under the same lock. Operation activation takes it as its first statement.
    """
    connection.execute(
        select(applications.c.id).where(applications.c.id == application_id).with_for_update()
    ).one_or_none()


def _active_plan(
    connection: Connection,
    application_id: str,
    expected_selection_plan_id: str | None,
    enforce_expected_selection_plan: bool = False,
    compatible_job_analysis_id: str | None = None,
) -> SelectionPlan | None:
    """The active plan, refusing if it moved since the decision was made.

    `expected_selection_plan_id` is the optimistic check: it is the plan the
    user was looking at when they decided. If the active plan has moved on,
    the command is refused rather than quietly rebased onto something the
    user never saw. One implementation, because both plan writers make the
    same promise about it. A replacement plan compares only with a plan for
    its analysis; an older analysis's historical plan is not active for it.
    """
    row = (
        connection.execute(
            select(selection_plans)
            .where(selection_plans.c.application_id == application_id)
            .order_by(selection_plans.c.version_number.desc())
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    latest = _selection_plan_record(row) if row is not None else None
    guarded_latest = (
        latest
        if latest is not None
        and (
            compatible_job_analysis_id is None
            or latest.job_analysis_id == compatible_job_analysis_id
        )
        else None
    )
    if (enforce_expected_selection_plan or expected_selection_plan_id is not None) and (
        (guarded_latest.id if guarded_latest is not None else None) != expected_selection_plan_id
    ):
        raise StateConflict(
            "the active SelectionPlan moved since this decision was made "
            "(expected_selection_plan_id): expected "
            f"{expected_selection_plan_id}, found "
            f"{guarded_latest.id if guarded_latest else 'none'}"
        )
    return latest


def _assert_matching_context(
    connection: Connection,
    application_id: str,
    *,
    expected_analysis_id: str | None,
    expected_selection_plan_id: str | None,
    enforce_expected_selection_plan: bool,
    refuse_matching_context_operation: bool,
) -> None:
    """CAS both active records while the Application row is locked.

    A fresh analyze passes no expected analysis and is unaffected. An
    explicit decision passes both observed identities; checking them in
    the same transaction that inserts the replacements prevents a stale
    browser tab from reviving an older context.
    """
    if expected_analysis_id is not None:
        active_snapshot_id = connection.execute(
            select(job_snapshots.c.id)
            .where(job_snapshots.c.application_id == application_id)
            .order_by(job_snapshots.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        active_analysis_id = connection.execute(
            select(job_analyses.c.id)
            .where(
                job_analyses.c.application_id == application_id,
                job_analyses.c.job_snapshot_id == active_snapshot_id,
            )
            .order_by(job_analyses.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        if active_analysis_id != expected_analysis_id:
            raise StateConflict(
                "the active JobAnalysis moved since this decision was made "
                "(expected_analysis_id): "
                f"expected {expected_analysis_id}, found {active_analysis_id or 'none'}"
            )
    _active_plan(
        connection,
        application_id,
        expected_selection_plan_id,
        enforce_expected_selection_plan,
        compatible_job_analysis_id=expected_analysis_id,
    )
    if refuse_matching_context_operation:
        _refuse_matching_context_operation(connection, application_id)


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


def _insert_selection_plan(
    connection: Connection,
    selection_plan_id: str,
    application_id: str,
    job_analysis_id: str,
    plan: SelectionManifest,
    candidate_context_version: str,
    candidate_context_hash: str,
    profile_version: str,
    selection_policy_version: str,
    track_emphasis_dependencies: dict[str, str],
    created_at: str,
) -> None:
    analysis = (
        connection.execute(
            select(job_analyses.c.application_id).where(job_analyses.c.id == job_analysis_id)
        )
        .mappings()
        .one_or_none()
    )
    if analysis is None or analysis["application_id"] != application_id:
        raise LineageBroken(
            "a selection plan cannot reference a job analysis belonging to another application"
        )
    version = connection.execute(
        select(
            (func.coalesce(func.max(selection_plans.c.version_number), 0) + 1).label("version")
        ).where(selection_plans.c.application_id == application_id)
    ).scalar_one()
    connection.execute(
        insert(selection_plans).values(
            id=selection_plan_id,
            application_id=application_id,
            job_analysis_id=job_analysis_id,
            version_number=version,
            plan_json=plan.model_dump(mode="json"),
            candidate_context_version=candidate_context_version,
            candidate_context_hash=candidate_context_hash,
            profile_version=profile_version,
            selection_policy_version=selection_policy_version,
            track_emphasis_dependencies_json=track_emphasis_dependencies,
            created_at=created_at,
        )
    )


def _selection_plan_record(row: Any) -> SelectionPlan:
    if row is None:
        raise UnknownRecord("selection plan does not exist")
    record = dict(row)
    return SelectionPlan(
        id=record["id"],
        application_id=record["application_id"],
        job_analysis_id=record["job_analysis_id"],
        version_number=record["version_number"],
        plan=SelectionManifest.model_validate(record["plan_json"]),
        candidate_context_version=record["candidate_context_version"],
        candidate_context_hash=record["candidate_context_hash"],
        profile_version=record["profile_version"],
        selection_policy_version=record["selection_policy_version"],
        track_emphasis_dependencies=record["track_emphasis_dependencies_json"],
        created_at=record["created_at"],
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
    plan: SelectionManifest,
    *,
    provider: str,
    model: str,
    candidate_context_version: str,
    candidate_context_hash: str,
    profile_version: str,
    selection_policy_version: str,
    track_emphasis_dependencies: dict[str, str],
    expected_analysis_id: str | None = None,
    expected_selection_plan_id: str | None = None,
    enforce_expected_selection_plan: bool = False,
    refuse_matching_context_operation: bool = False,
) -> tuple[str, SelectionPlan]:
    """Write one analysis and its initial plan as a single record.

    The requirement ids are ids and not records: the acceptance names the
    analysis it was made against, and that analysis is allocated here. The
    caller has already refused any id that does not name a hard gap of the
    analysis being written, so what arrives is a decision about gaps this
    analysis actually states.
    """
    analysis_id = new_id()
    selection_plan_id = new_id()
    now = utc_now()
    _lock_application(connection, application_id)
    _assert_matching_context(
        connection,
        application_id,
        expected_analysis_id=expected_analysis_id,
        expected_selection_plan_id=expected_selection_plan_id,
        enforce_expected_selection_plan=enforce_expected_selection_plan,
        refuse_matching_context_operation=refuse_matching_context_operation,
    )
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
    _insert_selection_plan(
        connection,
        selection_plan_id,
        application_id,
        analysis_id,
        plan,
        candidate_context_version,
        candidate_context_hash,
        profile_version,
        selection_policy_version,
        track_emphasis_dependencies,
        now,
    )
    connection.execute(
        update(applications)
        .where(applications.c.id == application_id)
        # Classification only. Fit and the classification confidence
        # used to be copied here as well, which made the row a second
        # place the same answer was stored and could drift from the
        # analysis it was derived from. Fit is projected from the
        # requirements where it is read (`analysis/projection.py`), and
        # no confidence is reported at all under this contract.
        .values(
            language=analysis.language,
            track=analysis.track.value,
            profile=analysis.profile.value,
            emphasis=analysis.emphasis.value,
            updated_at=now,
        )
    )
    plan_row = (
        connection.execute(select(selection_plans).where(selection_plans.c.id == selection_plan_id))
        .mappings()
        .one_or_none()
    )
    return analysis_id, _selection_plan_record(plan_row)


def _create_selection_plan(
    connection: Connection,
    application_id: str,
    job_analysis_id: str,
    plan: SelectionManifest,
    *,
    candidate_context_version: str,
    candidate_context_hash: str,
    profile_version: str,
    selection_policy_version: str,
    track_emphasis_dependencies: dict[str, str],
    expected_selection_plan_id: str | None = None,
    enforce_expected_selection_plan: bool = False,
    refuse_matching_context_operation: bool = False,
    plan_id: str | None = None,
    created_at: str | None = None,
) -> SelectionPlan:
    selection_plan_id = plan_id or new_id()
    now = created_at or utc_now()
    # The standing acceptances are read, merged and written inside one
    # transaction. Reading them outside it let a later writer compute a
    # legal new version from a plan it had already been overtaken on,
    # dropping an acceptance with no error and no trace: the version
    # number is allocated here, so the unique constraint never fires.
    _lock_application(connection, application_id)
    active_snapshot_id = connection.execute(
        select(job_snapshots.c.id)
        .where(job_snapshots.c.application_id == application_id)
        .order_by(job_snapshots.c.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    active_analysis_id = connection.execute(
        select(job_analyses.c.id)
        .where(
            job_analyses.c.application_id == application_id,
            job_analyses.c.job_snapshot_id == active_snapshot_id,
        )
        .order_by(job_analyses.c.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    if active_analysis_id != job_analysis_id:
        raise StateConflict(
            "the active JobAnalysis moved before the SelectionPlan was created: "
            f"expected {job_analysis_id}, found {active_analysis_id or 'none'}"
        )
    if refuse_matching_context_operation:
        _refuse_matching_context_operation(connection, application_id)
    # Read for its refusal, not for its value. The acceptance carry that
    # used to call it is gone, and with it went the optimistic check it
    # performed on the way: a decision made against a plan that has
    # since moved must still be refused rather than quietly rebased onto
    # one the user never saw.
    _active_plan(
        connection,
        application_id,
        expected_selection_plan_id,
        enforce_expected_selection_plan,
        compatible_job_analysis_id=job_analysis_id,
    )
    existing = (
        connection.execute(select(selection_plans).where(selection_plans.c.id == selection_plan_id))
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        stored = _selection_plan_record(existing)
        expected = {
            "application_id": application_id,
            "job_analysis_id": job_analysis_id,
            "plan": plan,
            "candidate_context_version": candidate_context_version,
            "candidate_context_hash": candidate_context_hash,
            "profile_version": profile_version,
            "selection_policy_version": selection_policy_version,
            "track_emphasis_dependencies": track_emphasis_dependencies,
            "created_at": now,
        }
        actual = {key: getattr(stored, key) for key in expected}
        if actual != expected:
            raise StateConflict("selection plan identity already has different content")
        return stored
    _insert_selection_plan(
        connection,
        selection_plan_id,
        application_id,
        job_analysis_id,
        plan,
        candidate_context_version,
        candidate_context_hash,
        profile_version,
        selection_policy_version,
        track_emphasis_dependencies,
        now,
    )
    if plan.emphasis_override is not None:
        # Application.emphasis is the current matching configuration,
        # not immutable analysis history. An Emphasis-only decision
        # therefore advances it with the active plan while leaving the
        # JobAnalysis row untouched.
        connection.execute(
            update(applications)
            .where(applications.c.id == application_id)
            .values(emphasis=plan.emphasis.value, updated_at=now)
        )
    row = (
        connection.execute(select(selection_plans).where(selection_plans.c.id == selection_plan_id))
        .mappings()
        .one_or_none()
    )
    return _selection_plan_record(row)
