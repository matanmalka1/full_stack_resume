"""The application -> snapshot -> analysis -> draft -> approval -> decision chain.

Every test here asserts two things about a rejected operation: that it is
rejected, and that it left nothing behind. A guard that raises after writing an
artifact, a decision, an analysis, or an application field is not a guard.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.infrastructure.db import connect
from cv_engine.domain.draft_markdown import parse_draft
from cv_engine.application.ready import verify_ready_integrity
from cv_engine.runtime.workspace import Workspace
from cv_engine.runtime.composition import Services
from cv_engine.application.errors import WorkflowError
from helpers import ACCOUNT_MANAGER_JOB


PERSISTED_TABLES = (
    "job_snapshots",
    "job_analyses",
    "status_history",
    "application_events",
    "decision_records",
    "generation_runs",
    "validation_runs",
)


def _rows(services: Services, sql: str, *params) -> list[dict]:
    with connect(services.repository.path) as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def _persisted(services: Services, application_id: str) -> dict[str, int]:
    """Everything this application could have written, counted in one place."""
    counts = {
        table: len(_rows(services, f"SELECT 1 FROM {table} WHERE application_id=?", application_id))
        for table in PERSISTED_TABLES
    }
    counts["artifact_versions"] = len(services.repository.artifact_versions(application_id))
    return counts


def _analyze(services: Services, application_id: str, **overrides):
    snapshot_id = services.repository.latest_snapshot(application_id)["id"]
    return services.analysis.analyze(AnalyzeCommand(
        application_id=application_id,
        job_snapshot_id=snapshot_id,
        track_override=overrides.get("track"),
        profile_override=overrides.get("profile"),
        emphasis_override=overrides.get("emphasis"),
        language_override=overrides.get("language"),
    ))


def _draft(services: Services, application_id: str, analysis_id: str):
    return services.drafts.draft(DraftCommand(
        application_id=application_id,
        job_analysis_id=analysis_id,
    ))


# --- 1. a new job snapshot requires a new analysis before drafting ---------


def test_new_snapshot_requires_a_new_analysis_before_drafting(
    v1_repo: Path, analyzed_application
) -> None:
    services, app_id = analyzed_application("Snapshot Race")
    stale_analysis_id, _ = services.repository.latest_analysis(app_id)
    new_snapshot_id = services.repository.add_job_snapshot(
        app_id, ACCOUNT_MANAGER_JOB + " The role also covers quarterly portfolio reviews."
    )
    before = _persisted(services, app_id)

    with pytest.raises(WorkflowError, match="snapshot"):
        _draft(services, app_id, stale_analysis_id)

    assert not (v1_repo / "artifacts/working" / app_id).exists()
    assert _persisted(services, app_id) == before

    # Analyzing the new snapshot unblocks drafting, and the draft binds both ends
    # of the chain exactly rather than inheriting a "latest" of either kind.
    analysed = _analyze(services, app_id)
    assert analysed.analysis_id != stale_analysis_id
    drafted = _draft(services, app_id, analysed.analysis_id)
    manifest = services.artifacts.working_paths(app_id).manifest
    assert drafted.validation.passed, drafted.validation.model_dump()
    draft = parse_draft(manifest.read_text(encoding="utf-8"))
    assert draft.job_analysis_id == analysed.analysis_id
    assert draft.job_snapshot_id == new_snapshot_id


# --- 2. a newer material analysis invalidates an older working draft -------


def test_newer_material_analysis_invalidates_the_working_draft(
    v1_repo: Path, drafted_application
) -> None:
    setup = drafted_application("Emphasis Drift")
    services, app_id = setup.services, setup.application_id
    drafted_analysis_id = parse_draft(setup.manifest.read_text(encoding="utf-8")).job_analysis_id
    newer = _analyze(services, app_id, emphasis="balanced-sales")
    assert newer.analysis.emphasis.value == "balanced-sales"
    assert newer.analysis_id != drafted_analysis_id
    before = _persisted(services, app_id)

    with pytest.raises(WorkflowError, match="analysis"):
        services.drafts.approve(app_id)

    assert not (v1_repo / "artifacts" / app_id).exists()
    assert _persisted(services, app_id) == before

    # Re-drafting under the newer analysis is the way forward, and the decision
    # record then binds that analysis.
    drafted = _draft(services, app_id, newer.analysis_id)
    manifest = services.artifacts.working_paths(app_id).manifest
    assert drafted.validation.passed, drafted.validation.model_dump()
    assert parse_draft(manifest.read_text(encoding="utf-8")).job_analysis_id == newer.analysis_id
    services.drafts.approve(app_id)
    assert services.repository.latest_decision(app_id)["job_analysis_id"] == newer.analysis_id


def test_approval_binds_the_draft_analysis_not_the_latest(drafted_application) -> None:
    """A re-run that changes nothing material leaves the draft valid -- and the
    approval still records the analysis the draft was actually built from."""
    setup = drafted_application("Rerun Analysis")
    services, app_id = setup.services, setup.application_id
    bound_analysis_id = parse_draft(setup.manifest.read_text(encoding="utf-8")).job_analysis_id
    rerun = _analyze(services, app_id)
    assert rerun.analysis_id != bound_analysis_id

    services.drafts.approve(app_id)

    decision = services.repository.latest_decision(app_id)
    assert decision["job_analysis_id"] == bound_analysis_id
    assert json.loads(decision["structured_json"])["job_analysis_id"] == bound_analysis_id


# --- 3. records may not cross application ownership boundaries -------------


def test_foreign_working_draft_cannot_be_approved(v1_repo: Path, drafted_application) -> None:
    target = drafted_application("Target Co")
    other = drafted_application("Other Co", role="Key Account Manager")
    services = target.services
    working = v1_repo / "artifacts/working"
    for name in ("resume.md", "resume.claims.json"):
        shutil.copy2(working / other.application_id / name, working / target.application_id / name)
    before_target = _persisted(services, target.application_id)
    before_other = _persisted(services, other.application_id)

    with pytest.raises(WorkflowError, match="application"):
        services.drafts.approve(target.application_id)

    assert not (v1_repo / "artifacts" / target.application_id).exists()
    assert _persisted(services, target.application_id) == before_target
    assert _persisted(services, other.application_id) == before_other
    assert _rows(services, "SELECT 1 FROM decision_records") == []


def test_decision_and_artifact_records_cannot_cross_applications(drafted_application) -> None:
    owner = drafted_application("Owner Co")
    stranger = drafted_application("Stranger Co", role="Key Account Manager")
    services = owner.services
    services.drafts.approve(owner.application_id)
    owner_markdown = services.repository.latest_artifact_version(
        owner.application_id, "resume_markdown", "approved"
    )
    stranger_snapshot_id = services.repository.latest_snapshot(stranger.application_id)["id"]
    stranger_analysis_id, _ = services.repository.latest_analysis(stranger.application_id)
    owner_snapshot_id = services.repository.latest_snapshot(owner.application_id)["id"]
    owner_analysis_id, _ = services.repository.latest_analysis(owner.application_id)
    before = _persisted(services, stranger.application_id)

    # A foreign artifact version, a foreign snapshot, and a foreign analysis are
    # each rejected on their own.
    with pytest.raises(ValueError, match="application"):
        services.repository.record_decision(
            stranger.application_id, owner_markdown["id"], stranger_snapshot_id,
            stranger_analysis_id, {}, "foreign artifact version",
        )
    with pytest.raises(ValueError, match="application"):
        services.repository.record_decision(
            owner.application_id, owner_markdown["id"], stranger_snapshot_id,
            owner_analysis_id, {}, "foreign snapshot",
        )
    with pytest.raises(ValueError, match="application"):
        services.repository.record_decision(
            owner.application_id, owner_markdown["id"], owner_snapshot_id,
            stranger_analysis_id, {}, "foreign analysis",
        )
    with pytest.raises(ValueError, match="application"):
        services.repository.register_artifact_version(
            owner.application_id, "resume_markdown", "cross-owner",
            "artifacts/cross-owner.md", "0" * 64, "approved",
            job_snapshot_id=stranger_snapshot_id,
        )

    assert _persisted(services, stranger.application_id) == before
    assert [row["application_id"] for row in _rows(services, "SELECT * FROM decision_records")] == [
        owner.application_id
    ]


# --- 4. an invalid Track/Profile/Emphasis pair mutates nothing -------------


def test_invalid_classifications_are_rejected_before_any_persistence(services: Services) -> None:
    cases = [
        ({"track": "development", "profile": "account-manager"}, "Track"),
        ({"profile": "account-manager", "emphasis": "leadership"}, "mphasis"),
    ]
    for index, (overrides, match) in enumerate(cases):
        ingested = services.applications.ingest(IngestCommand(
            company=f"Inconsistent Co {index}",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
        ))
        app_id = ingested.application_id
        before_application = services.repository.get_application(app_id)
        before = _persisted(services, app_id)
        with pytest.raises(WorkflowError, match=match):
            _analyze(services, app_id, **overrides)
        assert services.repository.get_application(app_id) == before_application
        assert _persisted(services, app_id) == before
        with pytest.raises(KeyError):
            services.repository.latest_analysis(app_id)


# --- the chain is validated as one unit ------------------------------------


def test_working_draft_must_match_every_bound_analysis_dimension(
    v1_repo: Path, drafted_application
) -> None:
    setup = drafted_application("Tampered Chain")
    services, app_id = setup.services, setup.application_id
    manifest = v1_repo / "artifacts/working" / app_id / "resume.claims.json"
    original = manifest.read_text(encoding="utf-8")
    before = _persisted(services, app_id)
    cases = [
        ("track", "development"),
        ("emphasis", "balanced-sales"),
        ("language", "he"),
        ("job_snapshot_id", "not-a-snapshot"),
        ("fact_store_version", "0" * 64),
    ]
    for field, value in cases:
        payload = json.loads(original)
        payload[field] = value
        manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(WorkflowError):
            services.drafts.approve(app_id)
        assert not (v1_repo / "artifacts" / app_id).exists()
        assert _persisted(services, app_id) == before
    manifest.write_text(original, encoding="utf-8")


# --- ready integrity independently rechecks the chain ----------------------


def test_ready_integrity_rechecks_the_chain_after_a_material_reanalysis(
    workspace: Workspace, ready_application
) -> None:
    services, app_id = ready_application("Chain Recheck")
    assert verify_ready_integrity(
        services.artifacts, services.knowledge, services.repository, app_id
    ).passed

    _analyze(services, app_id, emphasis="balanced-sales")

    report = verify_ready_integrity(
        services.artifacts, services.knowledge, services.repository, app_id
    )
    assert not report.passed
    assert any(issue.code == "new-analysis-since-approval" for issue in report.issues)


def test_ready_integrity_holds_through_an_immaterial_reanalysis(
    workspace: Workspace, ready_application
) -> None:
    """A re-run that changes nothing material is not a reason to fail integrity."""
    services, app_id = ready_application("Immaterial Rerun")
    _analyze(services, app_id)
    report = verify_ready_integrity(
        services.artifacts, services.knowledge, services.repository, app_id
    )
    assert report.passed, report.model_dump()
