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
from pydantic import ValidationError

from cv_engine.chain import check_draft_chain, decision_record_analysis_id
from cv_engine.db import connect
from cv_engine.drafts import load_draft, serialize_markdown
from cv_engine.models import DraftDocument
from cv_engine.ready import verify_ready_integrity
from cv_engine.workflow import Engine, WorkflowError
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


def _rows(engine: Engine, sql: str, *params) -> list[dict]:
    with connect(engine.repo.path) as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def _persisted(engine: Engine, application_id: str) -> dict[str, int]:
    """Everything this application could have written, counted in one place."""
    counts = {
        table: len(_rows(engine, f"SELECT 1 FROM {table} WHERE application_id=?", application_id))
        for table in PERSISTED_TABLES
    }
    counts["artifact_versions"] = len(engine.repo.artifact_versions(application_id))
    return counts


# --- 1. a new job snapshot requires a new analysis before drafting ---------


def test_new_snapshot_requires_a_new_analysis_before_drafting(
    v1_repo: Path, analyzed_application
) -> None:
    engine, app_id = analyzed_application("Snapshot Race")
    stale_analysis_id, _ = engine.repo.latest_analysis(app_id)
    new_snapshot_id = engine.repo.add_job_snapshot(
        app_id, ACCOUNT_MANAGER_JOB + " The role also covers quarterly portfolio reviews."
    )
    before = _persisted(engine, app_id)

    with pytest.raises(WorkflowError, match="snapshot"):
        engine.draft(app_id)

    assert not (v1_repo / "artifacts/working" / app_id).exists()
    assert _persisted(engine, app_id) == before

    # Analyzing the new snapshot unblocks drafting, and the draft binds both ends
    # of the chain exactly rather than inheriting a "latest" of either kind.
    analysis_id, _ = engine.analyze(app_id)
    assert analysis_id != stale_analysis_id
    _markdown, manifest, report = engine.draft(app_id)
    assert report.passed, report.model_dump()
    draft = load_draft(manifest)
    assert draft.job_analysis_id == analysis_id
    assert draft.job_snapshot_id == new_snapshot_id


# --- 2. a newer material analysis invalidates an older working draft -------


def test_newer_material_analysis_invalidates_the_working_draft(
    v1_repo: Path, drafted_application
) -> None:
    setup = drafted_application("Emphasis Drift")
    engine, app_id = setup.engine, setup.application_id
    drafted_analysis_id = load_draft(setup.manifest).job_analysis_id
    newer_analysis_id, newer = engine.analyze(app_id, emphasis="balanced-sales")
    assert newer.emphasis.value == "balanced-sales"
    assert newer_analysis_id != drafted_analysis_id
    before = _persisted(engine, app_id)

    with pytest.raises(WorkflowError, match="analysis"):
        engine.approve(app_id)

    assert not (v1_repo / "artifacts" / app_id).exists()
    assert _persisted(engine, app_id) == before

    # Re-drafting under the newer analysis is the way forward, and the decision
    # record then binds that analysis.
    _markdown, manifest, report = engine.draft(app_id)
    assert report.passed, report.model_dump()
    assert load_draft(manifest).job_analysis_id == newer_analysis_id
    engine.approve(app_id)
    assert engine.repo.latest_decision(app_id)["job_analysis_id"] == newer_analysis_id


def test_approval_binds_the_draft_analysis_not_the_latest(drafted_application) -> None:
    """A re-run that changes nothing material leaves the draft valid -- and the
    approval still records the analysis the draft was actually built from."""
    setup = drafted_application("Rerun Analysis")
    engine, app_id = setup.engine, setup.application_id
    bound_analysis_id = load_draft(setup.manifest).job_analysis_id
    rerun_analysis_id, _ = engine.analyze(app_id)
    assert rerun_analysis_id != bound_analysis_id

    engine.approve(app_id)

    decision = engine.repo.latest_decision(app_id)
    assert decision["job_analysis_id"] == bound_analysis_id
    assert json.loads(decision["structured_json"])["job_analysis_id"] == bound_analysis_id


# --- 3. records may not cross application ownership boundaries -------------


def test_foreign_working_draft_cannot_be_approved(v1_repo: Path, drafted_application) -> None:
    target = drafted_application("Target Co")
    other = drafted_application("Other Co", role="Key Account Manager")
    engine = target.engine
    working = v1_repo / "artifacts/working"
    for name in ("resume.md", "resume.claims.json"):
        shutil.copy2(working / other.application_id / name, working / target.application_id / name)
    before_target = _persisted(engine, target.application_id)
    before_other = _persisted(engine, other.application_id)

    with pytest.raises(WorkflowError, match="application"):
        engine.approve(target.application_id)

    assert not (v1_repo / "artifacts" / target.application_id).exists()
    assert _persisted(engine, target.application_id) == before_target
    assert _persisted(engine, other.application_id) == before_other
    assert _rows(engine, "SELECT 1 FROM decision_records") == []


def test_decision_and_artifact_records_cannot_cross_applications(drafted_application) -> None:
    owner = drafted_application("Owner Co")
    stranger = drafted_application("Stranger Co", role="Key Account Manager")
    engine = owner.engine
    engine.approve(owner.application_id)
    owner_markdown = engine.repo.latest_artifact_version(
        owner.application_id, "resume_markdown", "approved"
    )
    stranger_snapshot_id = engine.repo.latest_snapshot(stranger.application_id)["id"]
    stranger_analysis_id, _ = engine.repo.latest_analysis(stranger.application_id)
    owner_snapshot_id = engine.repo.latest_snapshot(owner.application_id)["id"]
    owner_analysis_id, _ = engine.repo.latest_analysis(owner.application_id)
    before = _persisted(engine, stranger.application_id)

    # A foreign artifact version, a foreign snapshot, and a foreign analysis are
    # each rejected on their own.
    with pytest.raises(ValueError, match="application"):
        engine.repo.record_decision(
            stranger.application_id, owner_markdown["id"], stranger_snapshot_id,
            stranger_analysis_id, {}, "foreign artifact version",
        )
    with pytest.raises(ValueError, match="application"):
        engine.repo.record_decision(
            owner.application_id, owner_markdown["id"], stranger_snapshot_id,
            owner_analysis_id, {}, "foreign snapshot",
        )
    with pytest.raises(ValueError, match="application"):
        engine.repo.record_decision(
            owner.application_id, owner_markdown["id"], owner_snapshot_id,
            stranger_analysis_id, {}, "foreign analysis",
        )
    with pytest.raises(ValueError, match="application"):
        engine.repo.register_artifact_version(
            owner.application_id, "resume_markdown", "cross-owner",
            "artifacts/cross-owner.md", "0" * 64, "approved",
            job_snapshot_id=stranger_snapshot_id,
        )

    assert _persisted(engine, stranger.application_id) == before
    assert [row["application_id"] for row in _rows(engine, "SELECT * FROM decision_records")] == [
        owner.application_id
    ]


# --- 4. an invalid Track/Profile/Emphasis pair mutates nothing -------------


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"track": "development", "profile": "account-manager"}, "Track"),
        ({"profile": "account-manager", "emphasis": "leadership"}, "mphasis"),
    ],
    ids=["track-profile", "profile-emphasis"],
)
def test_invalid_classification_is_rejected_before_any_persistence(
    engine: Engine, overrides: dict[str, str], match: str
) -> None:
    app_id, _ = engine.ingest("Inconsistent Co", "Account Manager", ACCOUNT_MANAGER_JOB)
    before_application = engine.repo.get_application(app_id)
    before = _persisted(engine, app_id)

    with pytest.raises(WorkflowError, match=match):
        engine.analyze(app_id, **overrides)

    assert engine.repo.get_application(app_id) == before_application
    assert _persisted(engine, app_id) == before
    with pytest.raises(KeyError):
        engine.repo.latest_analysis(app_id)


def test_fast_mode_rejects_an_invalid_pair_without_leaving_an_application(
    v1_repo: Path, engine: Engine
) -> None:
    with pytest.raises(WorkflowError, match="Track"):
        engine.fast(
            "Fast Inconsistent", "Account Manager", ACCOUNT_MANAGER_JOB,
            track="development", profile="account-manager",
        )
    applications = engine.repo.list_applications()
    assert [row["current_status"] for row in applications] == ["saved"]
    assert _persisted(engine, applications[0]["id"])["job_analyses"] == 0
    assert not (v1_repo / "artifacts/working").exists()


# --- the chain is validated as one unit ------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("track", "development"),
        ("emphasis", "balanced-sales"),
        ("language", "he"),
        ("job_snapshot_id", "not-a-snapshot"),
        ("fact_store_version", "0" * 64),
    ],
)
def test_working_draft_must_match_its_bound_analysis(
    v1_repo: Path, drafted_application, field: str, value: str
) -> None:
    setup = drafted_application("Tampered Chain")
    engine, app_id = setup.engine, setup.application_id
    manifest = v1_repo / "artifacts/working" / app_id / "resume.claims.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload[field] = value
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    before = _persisted(engine, app_id)

    with pytest.raises(WorkflowError):
        engine.approve(app_id)

    assert not (v1_repo / "artifacts" / app_id).exists()
    assert _persisted(engine, app_id) == before


def test_pre_binding_manifest_resolves_through_its_decision_record(
    v1_repo: Path, approved_application, fact_store, profile_store
) -> None:
    """Approved manifests written before `job_analysis_id` existed are immutable,
    so they must stay loadable -- and they recover their analysis from their own
    decision record rather than from whichever analysis is latest."""
    setup = approved_application("Pre-Binding Manifest")
    engine, app_id = setup.engine, setup.application_id
    payload = json.loads(
        (v1_repo / "artifacts" / app_id / "v001" / "resume.claims.json").read_text(encoding="utf-8")
    )
    bound_analysis_id = payload["job_analysis_id"]
    legacy = DraftDocument.model_validate(
        {**payload, "schema_version": "1.0", "job_analysis_id": None}
    )
    assert "job_analysis_id" not in serialize_markdown(legacy)

    orphan = check_draft_chain(engine.repo, app_id, legacy, profile_store, fact_store)
    assert [code for code, _ in orphan.problems] == ["unbound-draft-analysis"]

    chain = check_draft_chain(
        engine.repo, app_id, legacy, profile_store, fact_store,
        recorded_analysis_id=decision_record_analysis_id(engine.repo, app_id),
    )
    assert chain.valid, chain.describe()
    assert chain.bound()[0] == bound_analysis_id


def test_draft_chain_binding_is_immutable(drafted_application) -> None:
    setup = drafted_application("Immutable Binding")
    draft = load_draft(setup.manifest)
    for field in ("application_id", "job_snapshot_id", "job_analysis_id"):
        with pytest.raises(ValidationError):
            setattr(draft, field, "rebound")


# --- ready integrity independently rechecks the chain ----------------------


def test_ready_integrity_rechecks_the_chain_after_a_material_reanalysis(
    v1_repo: Path, ready_application
) -> None:
    engine, app_id = ready_application("Chain Recheck")
    assert verify_ready_integrity(v1_repo, engine.repo, app_id).passed

    engine.analyze(app_id, emphasis="balanced-sales")

    report = verify_ready_integrity(v1_repo, engine.repo, app_id)
    assert not report.passed
    assert any(issue.code == "new-analysis-since-approval" for issue in report.issues)


def test_ready_integrity_holds_through_an_immaterial_reanalysis(
    v1_repo: Path, ready_application
) -> None:
    """A re-run that changes nothing material is not a reason to fail integrity."""
    engine, app_id = ready_application("Immaterial Rerun")
    engine.analyze(app_id)
    report = verify_ready_integrity(v1_repo, engine.repo, app_id)
    assert report.passed, report.model_dump()
