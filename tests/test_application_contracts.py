"""Application-boundary invariants not already owned by API or persistence tests."""

from __future__ import annotations

import pytest
from helpers import ACCOUNT_MANAGER_JOB, seed_analysis_for_command

from cv_engine.application import errors
from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.util import sha256_file, sha256_text


def test_ingest_commits_exact_snapshot_payload_before_registration(
    services, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metadata row must never name a snapshot payload that was not committed."""
    received = "Line one\r\nLine two\n"
    original_commit = services.payloads.commit_snapshot

    def assert_payload_exists_first(application_id: str, snapshot_id: str, text: str):
        stored = original_commit(application_id, snapshot_id, text)
        payload = services.paths.root / stored.reference
        assert payload.read_bytes() == received.encode("utf-8")
        assert sha256_text(received) == stored.sha256
        with pytest.raises(errors.UnknownRecord):
            services.repository.get_application(application_id)
        return stored

    monkeypatch.setattr(services.payloads, "commit_snapshot", assert_payload_exists_first)
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


def test_ingest_database_records_roll_back_together_after_payload_commit(
    services, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse_initial_event(*args, **kwargs):
        raise RuntimeError("event refused")

    monkeypatch.setattr(
        services.applications._recruitment,
        "insert_initial_saved_event",
        refuse_initial_event,
    )

    with pytest.raises(RuntimeError, match="event refused"):
        services.applications.ingest(
            IngestCommand(
                company="Atomic Intake",
                target_role="Developer",
                job_text="Python and PostgreSQL",
                client="web",
            )
        )

    assert all(
        row["company"] != "Atomic Intake"
        for row in services.repository.list_applications(include_deleted=True)
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
