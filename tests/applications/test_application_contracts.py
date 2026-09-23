"""Application-boundary invariants not already owned by API or persistence tests."""

from __future__ import annotations

import pytest
from helpers import ACCOUNT_MANAGER_JOB, seed_analysis_for_command

from cv_engine.application import errors
from cv_engine.application.commands import (
    AnalyzeCommand,
    DraftCommand,
    IngestCommand,
)


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
