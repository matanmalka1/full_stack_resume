"""Document-state fixtures using the production composition root."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fake_provider import FakeOpenAI
from foreground import foreground_executor
from helpers import (
    ACCOUNT_MANAGER_JOB,
    analysis_proposal,
    approve_active_draft,
    seed_document,
    stored_document,
    validate_active_draft,
)

from cv_engine.application.commands import (
    AnalyzeCommand,
    DraftCommand,
    IngestCommand,
    RenderCommand,
    SubmissionCommand,
)
from cv_engine.domain.document import DocumentState
from cv_engine.runtime.composition import Services
from cv_engine.util import new_id, utc_now
from fixtures.models import WorkflowSetup


@pytest.fixture
def analyzed_application(ai_services: Services, fake_openai: FakeOpenAI):
    def build(company: str, role="Account Manager", job_text=ACCOUNT_MANAGER_JOB):
        fake_openai.script("propose_analysis", analysis_proposal())
        ingested = ai_services.applications.ingest(
            IngestCommand(
                company=company,
                target_role=role,
                job_text=job_text,
                acknowledged_duplicates=True,
                client="web",
            )
        )
        queued = ai_services.operation_submissions.submit_analysis(
            AnalyzeCommand(
                application_id=ingested.application_id,
                job_snapshot_id=ingested.job_snapshot_id,
            ),
            idempotency_key=new_id(),
            analysis_service=ai_services.analysis,
        )
        completed = foreground_executor(ai_services).execute(queued.id)
        assert completed.status.value == "succeeded", completed.safe_failure_detail
        document = stored_document(ai_services, ingested.application_id)
        return WorkflowSetup(
            ai_services,
            ingested.application_id,
            ingested.job_snapshot_id,
            analysis_id=document.analysis_id,
            document_hash=document.document_hash,
        )

    return build


@pytest.fixture
def document_created(services: Services):
    def build(company="Document Co", role="Account Manager", job_text=ACCOUNT_MANAGER_JOB):
        ingested, analysis = seed_document(services, company, role=role, job_text=job_text)
        document = stored_document(services, ingested.application_id)
        return WorkflowSetup(
            services,
            ingested.application_id,
            ingested.job_snapshot_id,
            analysis_id=analysis.analysis_id,
            document_hash=document.document_hash,
        )

    return build


@pytest.fixture
def drafted_application(document_created):
    def build(company="Draft Co", role="Account Manager", job_text=ACCOUNT_MANAGER_JOB):
        setup = document_created(company, role, job_text)
        drafted = setup.services.drafts.draft(
            DraftCommand(
                application_id=setup.application_id,
                expected_document_hash=setup.document_hash,
            )
        )
        return replace(setup, document_hash=drafted.document_hash)

    return build


@pytest.fixture
def document_checked(drafted_application):
    def build(company="Checked Co", role="Account Manager", job_text=ACCOUNT_MANAGER_JOB):
        setup = drafted_application(company, role, job_text)
        checked = validate_active_draft(setup.services, setup.application_id)
        assert checked.passed, checked.report
        return replace(setup, draft_report=checked.report)

    return build


@pytest.fixture
def approved_application(drafted_application):
    def build(company="Approved Co", role="Account Manager", job_text=ACCOUNT_MANAGER_JOB):
        setup = drafted_application(company, role, job_text)
        approved = approve_active_draft(setup.services, setup.application_id)
        assert approved.passed, approved.report
        return replace(setup, approved=approved)

    return build


@pytest.fixture
def artifact_approved_application(approved_application):
    return approved_application


@pytest.fixture
def ready_application(approved_application, deterministic_renderer):
    def build(company="Ready Co", role="Account Manager", job_text=ACCOUNT_MANAGER_JOB):
        setup = approved_application(company, role, job_text)
        rendered = setup.services.rendering.render(
            RenderCommand(
                application_id=setup.application_id,
                expected_document_hash=setup.document_hash,
            )
        )
        assert rendered.validation.passed, rendered.validation
        document = stored_document(setup.services, setup.application_id)
        assert document.pdf_path is not None
        assert (
            setup.services.queries.application_detail(setup.application_id).document_state
            is DocumentState.READY
        )
        return replace(
            setup,
            pdf=setup.services.paths.root / document.pdf_path,
            ready_report=rendered.validation,
        )

    return build


@pytest.fixture
def submitted_application(ready_application):
    def build(company="Submitted Co"):
        setup = ready_application(company)
        setup.services.submission.submit_application(
            SubmissionCommand(
                application_id=setup.application_id,
                expected_document_hash=setup.document_hash,
                submitted_at=utc_now(),
                client="web",
            )
        )
        return setup

    return build
