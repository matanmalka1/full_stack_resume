"""Application-boundary invariants not already owned by API or persistence tests."""

from __future__ import annotations

import pytest
from helpers import (
    ACCOUNT_MANAGER_JOB,
    seed_analysis_for_command,
    seed_existing_analysis,
    stored_document,
)

from cv_engine.application import errors
from cv_engine.application.commands import (
    AnalyzeCommand,
    BuildFromAnalysisCommand,
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
            job_text=f"{ACCOUNT_MANAGER_JOB}\nTheirs: a different posting.",
            acknowledged_duplicates=True,
            client="web",
        )
    )

    # An analysis names the job text it reads; another Application's text is not this
    # one's, so the command is refused before anything is read or written.
    with pytest.raises(errors.StateConflict, match="job text changed"):
        seed_analysis_for_command(
            services,
            AnalyzeCommand(
                application_id=mine.application_id,
                job_text_hash=theirs.job_text_hash,
            ),
        )

    analysed = seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=theirs.application_id,
            job_text_hash=theirs.job_text_hash,
        ),
    )
    seed_existing_analysis(services, mine)
    with pytest.raises(errors.LineageBroken):
        services.draft_editing.build_from_analysis(
            BuildFromAnalysisCommand(
                application_id=mine.application_id,
                analysis_id=analysed.analysis_id,
                expected_document_hash=stored_document(services, mine.application_id).document_hash,
            )
        )
