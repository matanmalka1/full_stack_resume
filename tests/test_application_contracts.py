"""Application-boundary invariants not already owned by API or persistence tests."""

from __future__ import annotations

import pytest
from helpers import ACCOUNT_MANAGER_JOB

from cv_engine.application import errors
from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.util import sha256_file, sha256_text


def test_ingest_commits_exact_snapshot_payload_before_registration(
    services, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metadata row must never name a snapshot payload that was not committed."""
    received = "Line one\r\nLine two\n"
    original_create = services.repository.create_application

    def assert_payload_exists_first(**values):
        payload = services.paths.root / values["payload_path"]
        assert payload.read_bytes() == received.encode("utf-8")
        assert sha256_text(received) == values["source_hash"]
        return original_create(**values)

    monkeypatch.setattr(services.repository, "create_application", assert_payload_exists_first)
    ingested = services.applications.ingest(
        IngestCommand(
            company="Payload Order",
            target_role="Developer",
            job_text=received,
            client="web",
        )
    )
    snapshot = services.repository.get_snapshot(ingested.job_snapshot_id)
    assert sha256_file(services.paths.root / snapshot["payload_path"]) == snapshot["source_hash"]


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
        services.analysis.analyze(
            AnalyzeCommand(
                application_id=mine.application_id,
                job_snapshot_id=theirs.job_snapshot_id,
            )
        )

    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=theirs.application_id,
            job_snapshot_id=theirs.job_snapshot_id,
        )
    )
    with pytest.raises(errors.LineageBroken):
        services.drafts.draft(
            DraftCommand(
                application_id=mine.application_id,
                job_analysis_id=analysed.analysis_id,
                selection_plan_id=analysed.selection_plan_id,
            )
        )
