from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from helpers import (
    ACCOUNT_MANAGER_JOB,
    approve_active_draft,
    artifact_version_and_path,
    seed_analysis_for_command,
)
from sqlalchemy import func, select

import cv_engine.infrastructure.rendering as rendering_module
from cv_engine.application.commands import (
    AnalyzeCommand,
    DraftCommand,
    ExternalSubmissionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    SubmissionCommand,
)
from cv_engine.application.errors import WorkflowError
from cv_engine.infrastructure.persistence.application_projections import (
    SqlAlchemyApplicationProjectionReader,
)
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.infrastructure.persistence.draft_lifecycle import (
    SqlAlchemyDraftLifecycleRepository,
)
from cv_engine.infrastructure.persistence.job_snapshots import SqlAlchemyJobSnapshotStore
from cv_engine.infrastructure.persistence.tables import submissions
from cv_engine.infrastructure.rendering import validate_rendered as real_validate_rendered
from cv_engine.util import normalized_text, sha256_file, sha256_text, utc_now, verify_payload


def _submission_command(services, transaction_manager, application_id: str) -> SubmissionCommand:
    with transaction_manager.read() as tx:
        revision = SqlAlchemyDraftLifecycleRepository(transaction_manager).latest_approved_revision(
            tx, application_id
        )
    with transaction_manager.read() as tx:
        pdf = SqlAlchemyArtifactCatalog(transaction_manager).artifact_version_for_revision(
            tx, revision.id, "resume_pdf", "rendered"
        )
    return SubmissionCommand(
        application_id=application_id,
        approved_revision_id=revision.id,
        pdf_artifact_version_id=pdf["id"],
        submitted_at="2026-08-19T10:00:00+00:00",
        client="web",
    )


def _reanalyze(services, transaction_manager, application_id: str):
    with transaction_manager.read() as tx:
        snapshot_id = SqlAlchemyApplicationProjectionReader(transaction_manager).latest_snapshot(
            tx, application_id
        )["id"]
    return seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=application_id,
            job_snapshot_id=snapshot_id,
        ),
    )


def _start_new_draft(services, transaction_manager, application_id: str):
    with transaction_manager.read() as tx:
        analysis_record = SqlAlchemyApplicationProjectionReader(transaction_manager).analyses(
            tx, application_id
        )[-1]
    analysis_id = analysis_record["id"]
    with transaction_manager.read() as tx:
        plan = SqlAlchemyApplicationProjectionReader(transaction_manager).latest_selection_plan(
            tx, application_id
        )
    return services.drafts.draft(
        DraftCommand(
            application_id=application_id,
            job_analysis_id=analysis_id,
            selection_plan_id=plan.id,
        )
    )


def test_payload_verification_classifies_ok_missing_and_tampered(tmp_path: Path) -> None:
    path = tmp_path / "payload"
    assert verify_payload(path, "unused") == "missing"
    path.write_bytes(b"original")
    expected = sha256_file(path)
    assert verify_payload(path, expected) == "ok"
    path.write_bytes(b"tampered")
    assert verify_payload(path, expected) == "tampered"


# --- READY ownership ---------------------------------------------------


def test_repository_cannot_manually_set_ready(analyzed_application, transaction_manager) -> None:
    services, app_id = analyzed_application("Repo Ready")
    assert not hasattr(SqlAlchemyApplicationStore(transaction_manager), "transition_status")
    with pytest.raises(WorkflowError):
        services.recruitment.transition_status(
            RecruitmentStatusCommand(application_id=app_id, target_status="ready", client="web")
        )
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationStore(transaction_manager).get_application(tx, app_id)[
                "current_status"
            ]
            == "saved"
        )


@pytest.mark.browser
def test_failed_post_render_validation_does_not_set_ready(
    approved_application, monkeypatch: pytest.MonkeyPatch, transaction_manager
) -> None:
    services, app_id = approved_application("Render Failure")

    def failing_validate_rendered(*args, **kwargs):
        report = real_validate_rendered(*args, **kwargs)
        return report.model_copy(
            update={
                "passed": False,
                "groups": {**report.groups, "ats": False},
            }
        )

    monkeypatch.setattr(rendering_module, "validate_rendered", failing_validate_rendered)
    rendered = services.rendering.render(app_id)
    assert not rendered.validation.passed
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationStore(transaction_manager).get_application(tx, app_id)[
                "current_status"
            ]
            == "saved"
        )
    assert not services.rendering.ready_qualification(app_id).ready_qualified


def test_no_repository_primitive_can_assert_ready_for_unlinked_pdf(
    project_root: Path, approved_application, transaction_manager
) -> None:
    """Ready has no write primitive and exact stored proof is always re-derived."""
    services, app_id = approved_application("Set Ready Bypass")
    _manifest, manifest_path = artifact_version_and_path(
        services, app_id, "claim_manifest", "approved"
    )
    directory = manifest_path.parent
    fake_pdf = directory / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    with transaction_manager.write() as tx:
        revision = SqlAlchemyDraftLifecycleRepository(transaction_manager).latest_approved_revision(
            tx, app_id
        )
        fake_version_id = SqlAlchemyArtifactCatalog(transaction_manager).register_artifact_version(
            tx,
            app_id,
            "resume_pdf",
            "resume",
            fake_pdf.relative_to(project_root).as_posix(),
            sha256_file(fake_pdf),
            "rendered",
            revision_id=revision.id,
        )
    assert not hasattr(SqlAlchemyApplicationStore(transaction_manager), "set_ready")
    assert not hasattr(SqlAlchemyApplicationStore(transaction_manager), "_set_ready")
    qualification = services.rendering.ready_qualification(
        app_id,
        pdf_artifact_version_id=fake_version_id,
    )
    assert not qualification.ready_qualified
    assert any(
        issue.code == "no-post-render-validation" for issue in qualification.validation.issues
    )
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationStore(transaction_manager).get_application(tx, app_id)[
                "current_status"
            ]
            == "saved"
        )


def test_public_workflow_cannot_restore_ready_after_tamper_without_fresh_render(
    project_root: Path, ready_application, transaction_manager
) -> None:
    """Stored validation alone cannot qualify a tampered immutable artifact."""
    services, app_id = ready_application("No Stale Restore")
    pdf_version, path = artifact_version_and_path(services, app_id, "resume_pdf", "rendered")
    path.write_bytes(path.read_bytes() + b"tampered")

    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationStore(transaction_manager).get_application(tx, app_id)[
                "current_status"
            ]
            == "saved"
        )
    assert not services.rendering.ready_qualification(app_id).ready_qualified
    with pytest.raises(WorkflowError, match="tampered Ready evidence"):
        services.submission.submit_application(
            _submission_command(services, transaction_manager, app_id)
        )
    # A new revision and render create new immutable evidence; the old PDF is
    # never reused or relinked.
    _start_new_draft(services, transaction_manager, app_id)
    approve_active_draft(services, app_id)
    rendered = services.rendering.render(app_id)
    assert rendered.validation.passed
    with transaction_manager.read() as tx:
        new_pdf_version = SqlAlchemyArtifactCatalog(transaction_manager).latest_artifact_version(
            tx, app_id, "resume_pdf", "rendered"
        )
    assert new_pdf_version["id"] != pdf_version["id"]


# --- Fresh ready verification -------------------------------------------


def test_untouched_ready_application_passes(ready_application) -> None:
    services, app_id = ready_application("Untouched")
    report = services.rendering.ready_report(app_id)
    assert report.passed, report.model_dump()
    assert all(report.groups.values())


def test_ready_integrity_rejects_missing_or_tampered_registered_artifacts(
    project_root: Path, ready_application
) -> None:
    cases = [
        ("resume_pdf", "rendered", "tamper", "pdf-tampered", "rendered_artifacts"),
        ("resume_markdown", "approved", "tamper", "approved-markdown-tampered", "approved_source"),
        ("claim_manifest", "approved", "tamper", "approved-manifest-tampered", "approved_source"),
        ("resume_html", "rendered", "tamper", "html-tampered", "rendered_artifacts"),
        ("resume_pdf", "rendered", "missing", "pdf-missing", "rendered_artifacts"),
        ("resume_html", "rendered", "missing", "html-missing", "rendered_artifacts"),
    ]
    for index, (artifact_type, state, mutation, issue_code, issue_group) in enumerate(cases):
        services, app_id = ready_application(f"Artifact Integrity {index}")
        _version, path = artifact_version_and_path(services, app_id, artifact_type, state)
        if mutation == "missing":
            path.unlink()
        else:
            path.write_bytes(path.read_bytes() + b"tampered")
        report = services.rendering.ready_report(app_id)
        assert not report.passed, issue_code
        issue = next(issue for issue in report.issues if issue.code == issue_code)
        assert issue.group == issue_group
        assert report.groups[issue_group] is False


def test_ready_qualification_is_independent_of_active_context(
    ready_application, transaction_manager
) -> None:
    services, app_id = ready_application("Superseded")
    with transaction_manager.read() as tx:
        old_revision = SqlAlchemyDraftLifecycleRepository(
            transaction_manager
        ).latest_approved_revision(tx, app_id)
    with transaction_manager.read() as tx:
        old_pdf = SqlAlchemyArtifactCatalog(transaction_manager).artifact_version_for_revision(
            tx, old_revision.id, "resume_pdf", "rendered"
        )
    _start_new_draft(services, transaction_manager, app_id)
    new_revision = approve_active_draft(services, app_id)
    assert not services.rendering.ready_qualification(app_id).ready_qualified
    old_qualification = services.rendering.ready_qualification(
        app_id, old_revision.id, old_pdf["id"]
    )
    assert old_qualification.ready_qualified

    new_text = ACCOUNT_MANAGER_JOB + " Updated requirements."
    snapshot_id = str(uuid.uuid4())
    payload = services.payloads.commit_snapshot(app_id, snapshot_id, new_text)
    with transaction_manager.write() as tx:
        SqlAlchemyJobSnapshotStore(transaction_manager).insert_next_snapshot(
            tx,
            application_id=app_id,
            payload_path=payload.reference,
            source_hash=payload.sha256,
            normalized_hash=sha256_text(normalized_text(new_text)),
            snapshot_id=snapshot_id,
            source_url=None,
            source_metadata={},
            captured_at=utc_now(),
        )
    _reanalyze(services, transaction_manager, app_id)
    assert services.rendering.ready_qualification(
        app_id, old_revision.id, old_pdf["id"]
    ).ready_qualified
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyDraftLifecycleRepository(transaction_manager)
            .latest_approved_revision(tx, app_id)
            .id
            == new_revision.revision_id
        )
    submitted = services.submission.submit_application(
        SubmissionCommand(
            application_id=app_id,
            approved_revision_id=old_revision.id,
            pdf_artifact_version_id=old_pdf["id"],
            submitted_at="2026-08-19T10:00:00+00:00",
            client="web",
        )
    )
    assert submitted.current_status == "applied"
    assert submitted.warnings == [
        "READY_REVISION_FOR_OLDER_SNAPSHOT",
        "READY_REVISION_FOR_OLDER_ANALYSIS",
        "READY_REVISION_FOR_OLDER_SELECTION_PLAN",
    ]


# --- APPLIED binding ------------------------------------------------------


def test_submission_binds_current_pdf_and_remains_immutable_after_later_versions(
    ready_application, transaction_manager, database_engine
) -> None:
    services, app_id = ready_application("Two Cycles")
    with transaction_manager.read() as tx:
        first_pdf = SqlAlchemyArtifactCatalog(transaction_manager).latest_artifact_version(
            tx, app_id, "resume_pdf", "rendered"
        )
    _start_new_draft(services, transaction_manager, app_id)
    approve_active_draft(services, app_id)
    second_render = services.rendering.render(app_id)
    assert second_render.validation.passed, second_render.validation.model_dump()
    with transaction_manager.read() as tx:
        second_pdf = SqlAlchemyArtifactCatalog(transaction_manager).latest_artifact_version(
            tx, app_id, "resume_pdf", "rendered"
        )
    assert second_pdf["id"] != first_pdf["id"]
    with transaction_manager.read() as tx:
        revision = SqlAlchemyDraftLifecycleRepository(transaction_manager).latest_approved_revision(
            tx, app_id
        )
    result = services.submission.submit_application(
        SubmissionCommand(
            application_id=app_id,
            approved_revision_id=revision.id,
            pdf_artifact_version_id=second_pdf["id"],
            submitted_at="2026-08-19T10:00:00+00:00",
            client="web",
        )
    )
    assert result.pdf_artifact_version_id == second_pdf["id"]
    submitted_pdf_id = result.pdf_artifact_version_id
    with database_engine.connect() as connection:
        before = (
            connection.execute(
                select(submissions.c.artifact_version_id).where(
                    submissions.c.application_id == app_id
                )
            )
            .scalars()
            .all()
        )
    assert before == [submitted_pdf_id]

    # A later approved version must not rewrite or relink the existing submission.
    _start_new_draft(services, transaction_manager, app_id)
    approve_active_draft(services, app_id)
    with database_engine.connect() as connection:
        after = (
            connection.execute(
                select(submissions.c.artifact_version_id).where(
                    submissions.c.application_id == app_id
                )
            )
            .scalars()
            .all()
        )
    assert after == [submitted_pdf_id]


def test_submission_and_applied_transition_roll_back_together(
    ready_application,
    monkeypatch: pytest.MonkeyPatch,
    transaction_manager,
    database_engine,
) -> None:
    from cv_engine.infrastructure.persistence.recruitment import SqlAlchemyRecruitmentRepository

    services, app_id = ready_application("Atomic Submission")

    def fail_status_write(*_args, **_kwargs) -> None:
        raise RuntimeError("injected status failure")

    monkeypatch.setattr(SqlAlchemyRecruitmentRepository, "insert_event", fail_status_write)
    with pytest.raises(RuntimeError, match="injected status failure"):
        services.submission.submit_application(
            _submission_command(services, transaction_manager, app_id)
        )

    with database_engine.connect() as connection:
        count = connection.execute(
            select(func.count())
            .select_from(submissions)
            .where(submissions.c.application_id == app_id)
        ).scalar_one()
    assert count == 0
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationStore(transaction_manager).get_application(tx, app_id)[
                "current_status"
            ]
            == "saved"
        )


def test_generic_status_transition_to_applied_is_always_blocked(
    ready_application, transaction_manager
) -> None:
    """The generic transition rejects applied unconditionally -- even supplying
    a real, currently-valid rendered PDF artifact version id must not work,
    because the generic transition has no way to perform the fresh integrity
    verification that SubmissionService performs. There is no parameter that can
    talk it into treating a caller-supplied id as trustworthy."""
    services, app_id = ready_application("Direct Applied With PDF")
    with pytest.raises(WorkflowError, match="submission-owned"):
        services.recruitment.transition_status(
            RecruitmentStatusCommand(
                application_id=app_id,
                target_status="applied",
                reason="direct bypass attempt",
                client="web",
            )
        )
    with transaction_manager.read() as tx:
        assert (
            SqlAlchemyApplicationStore(transaction_manager).get_application(tx, app_id)[
                "current_status"
            ]
            == "saved"
        )


def test_external_submission_never_fabricates_revision_or_artifact(
    analyzed_application, transaction_manager
) -> None:
    services, app_id = analyzed_application("External Submission")
    first = services.submission.record_external_submission(
        ExternalSubmissionCommand(
            application_id=app_id,
            submitted_at="2026-08-19T10:00:00+00:00",
            metadata={"source": "email confirmation"},
            client="web",
        )
    )
    second = services.submission.record_external_submission(
        ExternalSubmissionCommand(
            application_id=app_id,
            submitted_at="2026-08-19T11:00:00+00:00",
            client="web",
        )
    )
    assert first.current_status == second.current_status == "applied"
    with transaction_manager.read() as tx:
        submissions = SqlAlchemyApplicationProjectionReader(transaction_manager).submissions(
            tx, app_id
        )
    assert len(submissions) == 2
    assert all(row["submission_type"] == "external" for row in submissions)
    assert all(row["approved_revision_id"] is None for row in submissions)
    assert all(row["artifact_version_id"] is None for row in submissions)
    with transaction_manager.read() as tx:
        applied_events = [
            row
            for row in SqlAlchemyApplicationProjectionReader(
                transaction_manager
            ).recruitment_events(tx, app_id)
            if row["to_status"] == "applied"
        ]
    assert len(applied_events) == 1


def test_correction_is_append_only_and_terminal_outcome_survives_closed(
    analyzed_application, transaction_manager
) -> None:
    services, app_id = analyzed_application("Correction History")
    withdrawn = services.recruitment.transition_status(
        RecruitmentStatusCommand(
            application_id=app_id,
            target_status="withdrawn",
            reason="mistaken entry",
            occurred_at="2026-08-19T10:00:00+00:00",
            client="web",
        )
    )
    assert withdrawn.terminal_outcome == "withdrawn"
    with pytest.raises(WorkflowError, match="reason is required"):
        services.recruitment.correct_recruitment_status(
            RecruitmentCorrectionCommand(
                application_id=app_id,
                target_status="interview",
                corrects_event_id=withdrawn.event_id or "",
                reason=" ",
                client="web",
            )
        )
    corrected = services.recruitment.correct_recruitment_status(
        RecruitmentCorrectionCommand(
            application_id=app_id,
            target_status="interview",
            corrects_event_id=withdrawn.event_id or "",
            reason="status was entered on the wrong application",
            occurred_at="2026-08-19T10:05:00+00:00",
            client="web",
        )
    )
    assert corrected.current_status == "interview"
    assert corrected.terminal_outcome is None
    with transaction_manager.read() as tx:
        events = SqlAlchemyApplicationProjectionReader(transaction_manager).recruitment_events(
            tx, app_id
        )
    original = next(row for row in events if row["id"] == withdrawn.event_id)
    correction = next(row for row in events if row["id"] == corrected.event_id)
    assert original["to_status"] == "withdrawn"
    assert correction["corrects_event_id"] == original["id"]
    assert correction["reason"] == "status was entered on the wrong application"

    for target in ("offer", "accepted", "closed"):
        closed = services.recruitment.transition_status(
            RecruitmentStatusCommand(application_id=app_id, target_status=target, client="web")
        )
    assert closed.current_status == "closed"
    assert closed.terminal_outcome == "accepted"


def test_approval_audit_and_decision_markdown_are_exact(
    approved_application, transaction_manager
) -> None:
    setup = approved_application("Decision Export")
    revision_id = setup.approved.revision_id
    exported = setup.services.draft_history.export_decision_markdown(
        setup.application_id, revision_id
    )
    assert exported.approved_revision_id == revision_id
    assert f"`{revision_id}`" in exported.content
    assert "## Exact lineage" in exported.content
    assert sha256_text(exported.content) == exported.content_hash
    with transaction_manager.read() as tx:
        audits = SqlAlchemyApplicationProjectionReader(transaction_manager).audit_records(
            tx, setup.application_id
        )
    approval = next(row for row in audits if row["action"] == "approve_draft")
    assert approval["entity_id"] == revision_id
