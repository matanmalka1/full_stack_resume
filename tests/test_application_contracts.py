"""Application-boundary invariants not already owned by API or persistence tests."""

from __future__ import annotations

import pytest
from helpers import ACCOUNT_MANAGER_JOB, seed_analysis_for_command

from cv_engine.application import errors
from cv_engine.application.commands import (
    AnalyzeCommand,
    DraftCommand,
    IngestCommand,
    ValidateDraftCommand,
)


def test_validation_refuses_to_record_after_the_draft_changes(
    drafted_application,
    monkeypatch: pytest.MonkeyPatch,
    transaction_manager,
    draft_lifecycle_store,
    validation_store,
) -> None:
    setup = drafted_application("Validation Race Co")
    with transaction_manager.read() as tx:
        working = draft_lifecycle_store.active_working_draft(tx, setup.application_id)
        before = validation_store.latest_validation_for_working_draft(tx, working.id)

    from cv_engine.application.services.drafts import validation as validation_module

    original = validation_module.run_draft_validation

    def edit_while_validation_runs(*args, **kwargs):
        report = original(*args, **kwargs)
        setup.services.drafts._commit_edit(working, working.source)
        return report

    monkeypatch.setattr(validation_module, "run_draft_validation", edit_while_validation_runs)

    with pytest.raises(errors.StateConflict):
        setup.services.draft_validation.validate_draft(
            ValidateDraftCommand(
                working_draft_id=working.id,
                expected_edit_version=working.edit_version,
            )
        )

    with transaction_manager.read() as tx:
        after = validation_store.latest_validation_for_working_draft(tx, working.id)
    assert after is not None and before is not None
    assert after["id"] == before["id"]


def test_commands_require_sources_owned_by_the_named_application(services) -> None:
    mine = services.applications.ingest(
        IngestCommand(
            company="Mine Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            client="web",
        )
    )
    theirs = services.applications.ingest(
        IngestCommand(
            company="Theirs Co",
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
            client="web",
        )
    )

    with pytest.raises(errors.LineageBroken):
        seed_analysis_for_command(
            services,
            AnalyzeCommand(
                application_id=mine.application_id,
                job_snapshot_id=theirs.job_snapshot_id,
            ),
        )

    analysed = seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=theirs.application_id,
            job_snapshot_id=theirs.job_snapshot_id,
        ),
    )
    with pytest.raises(errors.LineageBroken):
        services.drafts.draft(
            DraftCommand(
                application_id=mine.application_id,
                job_analysis_id=analysed.analysis_id,
                selection_plan_id=analysed.selection_plan_id,
            )
        )
