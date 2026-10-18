"""`create_draft` fits the draft it writes to the Profile's page limit (product-spec §10).

The writer's choice is measured, and lines are dropped by the page-fit rule until
it fits; the Operation reports what happened and every line it dropped. Pages are
counted by `PageCountingRenderer`, so each test sets how many lines fit on a page.
"""

from __future__ import annotations

import math
from typing import cast

import pytest
from fake_provider import FakeOpenAI
from fake_renderer import PageCountingRenderer, evidence_lines
from foreground import foreground_executor
from helpers import (
    actor_of,
    composed_content,
    seed_analysis_for_command,
    stored_document,
)
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.application.errors import InfrastructureFailure
from cv_engine.application.operations import (
    ClaimReviewReason,
    OperationStatus,
    PageFitReport,
    RejectedClaimReview,
)
from cv_engine.application.services.drafts import authoring
from cv_engine.domain.drafts import draft_claims
from cv_engine.domain.page_fit import next_trim
from cv_engine.domain.render_validation import page_limit
from cv_engine.infrastructure.persistence.tables import operations
from cv_engine.util import new_id


def _renderer(services) -> PageCountingRenderer:
    return cast(PageCountingRenderer, services.drafts.renderer)


def _analyzed(services) -> str:
    ingested = services.applications.ingest(
        actor_of(services),
        IngestCommand(
            company=f"Page Fit {new_id()[:8]}",
            target_role="Account Manager",
            job_text=(
                "Account Manager responsible for retention and customer relationships.\n\n"
                "Requirements:\n- Fluent English."
            ),
            acknowledged_duplicates=True,
            client="web",
        ),
    )
    seed_analysis_for_command(
        services,
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_text_hash=ingested.job_text_hash,
        ),
    )
    return ingested.application_id


def _maximum(services, application_id: str) -> int:
    actor = actor_of(services)
    source = services.drafts.document_source(actor, application_id)
    knowledge = services.drafts.load_knowledge(actor)
    return page_limit(knowledge.profiles.get(source.analysis.profile))


def _create_draft(services, application_id: str):
    """Run one `create_draft` whose writer keeps and echoes the whole frame."""
    queued = services.operation_submissions.submit_draft(
        actor_of(services),
        DraftCommand(
            application_id=application_id,
            expected_document_hash=stored_document(services, application_id).document_hash,
            provider="openai",
        ),
        idempotency_key=new_id(),
        draft_service=services.drafts,
    )
    return foreground_executor(services).execute(queued.id)


def _content_ids(services, application_id: str) -> set[str]:
    content = stored_document(services, application_id).content
    assert content is not None
    return {claim.claim_id for claim in draft_claims(content)}


def test_a_draft_within_its_limit_is_written_as_chosen(ai_services, fake_openai) -> None:
    application_id = _analyzed(ai_services)
    frame_lines = evidence_lines(composed_content(ai_services, application_id))
    fake_openai.script_draft()

    completed = _create_draft(ai_services, application_id)

    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail
    assert completed.page_fit == PageFitReport(
        status="fits", pages=1, maximum=_maximum(ai_services, application_id)
    )
    assert _renderer(ai_services).measured == [frame_lines]
    content = stored_document(ai_services, application_id).content
    assert content is not None and evidence_lines(content) == frame_lines


def test_an_overflowing_draft_is_trimmed_until_it_fits_and_says_what_went(
    ai_services, fake_openai: FakeOpenAI
) -> None:
    application_id = _analyzed(ai_services)
    frame_lines = evidence_lines(composed_content(ai_services, application_id))
    maximum = _maximum(ai_services, application_id)
    # Over the limit as chosen, within it two lines shorter.
    _renderer(ai_services).claims_per_page = math.ceil((frame_lines - 2) / maximum)
    fake_openai.script_draft()

    completed = _create_draft(ai_services, application_id)

    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail
    report = completed.page_fit
    assert report is not None and report.status == "trimmed"
    assert report.maximum == maximum
    assert report.pages is not None and report.pages <= maximum
    assert 1 <= len(report.trimmed) <= 2
    held = _content_ids(ai_services, application_id)
    for line in report.trimmed:
        assert line.claim_id not in held
        assert line.text and line.section
    # The report is what the Operation recorded, not something recomputed on read.
    stored = ai_services.operation_lifecycle.get(actor_of(ai_services), completed.id)
    assert stored.page_fit == report


def test_measurement_stops_at_its_cap_and_writes_the_most_trimmed_draft(
    ai_services, fake_openai
) -> None:
    application_id = _analyzed(ai_services)
    frame_lines = evidence_lines(composed_content(ai_services, application_id))
    _renderer(ai_services).claims_per_page = 1
    fake_openai.script_draft()

    completed = _create_draft(ai_services, application_id)

    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail
    report = completed.page_fit
    assert report is not None and report.status == "over"
    assert len(_renderer(ai_services).measured) == authoring.MAX_PAGE_MEASUREMENTS
    assert len(report.trimmed) == authoring.MAX_PAGE_MEASUREMENTS - 1
    content = stored_document(ai_services, application_id).content
    assert content is not None
    assert evidence_lines(content) == frame_lines - len(report.trimmed)
    assert report.pages == evidence_lines(content)


def test_a_draft_with_nothing_left_to_drop_is_reported_over(
    ai_services, fake_openai, monkeypatch
) -> None:
    application_id = _analyzed(ai_services)
    _renderer(ai_services).claims_per_page = 1
    monkeypatch.setattr(authoring, "next_trim", lambda *_: None)
    fake_openai.script_draft()

    completed = _create_draft(ai_services, application_id)

    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail
    report = completed.page_fit
    assert report is not None and report.status == "over" and report.trimmed == []
    assert len(_renderer(ai_services).measured) == 1


def test_an_unmeasurable_draft_is_written_untrimmed_and_says_so(ai_services, fake_openai) -> None:
    application_id = _analyzed(ai_services)
    frame_lines = evidence_lines(composed_content(ai_services, application_id))
    _renderer(ai_services).failure = InfrastructureFailure("no browser here")
    fake_openai.script_draft()

    completed = _create_draft(ai_services, application_id)

    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail
    assert completed.page_fit == PageFitReport(
        status="unavailable", maximum=_maximum(ai_services, application_id)
    )
    content = stored_document(ai_services, application_id).content
    assert content is not None and evidence_lines(content) == frame_lines


def test_a_measurement_failing_mid_trim_keeps_the_untrimmed_draft(ai_services, fake_openai) -> None:
    application_id = _analyzed(ai_services)
    frame_lines = evidence_lines(composed_content(ai_services, application_id))
    renderer = _renderer(ai_services)
    renderer.claims_per_page = 1
    renderer.failure = InfrastructureFailure("browser crashed")
    renderer.fail_from = 2
    fake_openai.script_draft()

    completed = _create_draft(ai_services, application_id)

    assert completed.status is OperationStatus.SUCCEEDED, completed.safe_failure_detail
    report = completed.page_fit
    assert report is not None
    assert (report.status, report.pages, report.trimmed) == ("unavailable", frame_lines, [])
    content = stored_document(ai_services, application_id).content
    assert content is not None and evidence_lines(content) == frame_lines


@pytest.mark.parametrize("also_withheld", [False, True])
def test_a_trimmed_line_leaves_the_withheld_lines(ai_services, also_withheld: bool) -> None:
    application_id = _analyzed(ai_services)
    actor = actor_of(ai_services)
    frame = composed_content(ai_services, application_id)
    knowledge = ai_services.drafts.load_knowledge(actor)
    profile = knowledge.profiles.get(
        ai_services.drafts.document_source(actor, application_id).analysis.profile
    )
    first = next_trim(frame, profile, knowledge.facts)
    assert first is not None
    other = next(
        claim
        for section in frame.sections
        for claim in section.claims
        if claim.claim_id != first and claim.style not in {"heading", "date", "contact"}
    )

    def rejected(claim_id: str) -> RejectedClaimReview:
        return RejectedClaimReview(
            claim_id=claim_id, section="s", text="t", verdict="uncertain", sources=[]
        )

    withheld = ClaimReviewReason(
        claims=[rejected(first), *([rejected(other.claim_id)] if also_withheld else [])]
    )
    # Over as written, within the limit one line shorter.
    lines = evidence_lines(frame)
    maximum = page_limit(profile)
    renderer = _renderer(ai_services)
    renderer.claims_per_page = math.ceil((lines - 1) / maximum)
    assert math.ceil(lines / renderer.claims_per_page) > maximum

    fitted, remaining, report = ai_services.drafts._fit_to_pages(
        frame, withheld, profile, knowledge, None
    )

    assert report.status == "trimmed"
    assert [line.claim_id for line in report.trimmed] == [first]
    assert first not in {claim.claim_id for claim in draft_claims(fitted)}
    if also_withheld:
        assert remaining is not None
        assert [item.claim_id for item in remaining.claims] == [other.claim_id]
    else:
        assert remaining is None


def test_a_page_fit_report_is_recorded_only_on_a_succeeded_operation(
    ai_services, database_engine
) -> None:
    application_id = _analyzed(ai_services)
    queued = ai_services.operation_submissions.submit_draft(
        actor_of(ai_services),
        DraftCommand(
            application_id=application_id,
            expected_document_hash=stored_document(ai_services, application_id).document_hash,
            provider="openai",
        ),
        idempotency_key=new_id(),
        draft_service=ai_services.drafts,
    )
    report = PageFitReport(status="fits", pages=1, maximum=1).model_dump(mode="json")
    with pytest.raises(IntegrityError, match="ck_operations_page_fit_status"):
        with database_engine.begin() as connection:
            connection.execute(
                update(operations).where(operations.c.id == queued.id).values(page_fit=report)
            )
