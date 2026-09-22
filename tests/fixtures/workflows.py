from __future__ import annotations

from dataclasses import replace

import pytest
from fake_provider import FakeOpenAI
from foreground import foreground_executor
from helpers import (
    ACCOUNT_MANAGER_JOB,
    analysis_proposal,
    approve_active_draft,
    artifact_path,
    seed_existing_analysis,
    working_draft_paths,
)

from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.infrastructure.persistence import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.application_store import SqlAlchemyApplicationStore
from cv_engine.infrastructure.persistence.artifact_catalog import SqlAlchemyArtifactCatalog
from cv_engine.runtime.composition import Services
from cv_engine.util import new_id
from fixtures.models import WorkflowSetup


@pytest.fixture
def analyzed_application(ai_services: Services, fake_openai: FakeOpenAI, requirement_concepts):
    def build(
        company: str,
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
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
        if completed.status.value != "succeeded":
            raise AssertionError(
                f"analysis Operation failed: {completed.failure_code} "
                f"{completed.safe_failure_detail}"
            )
        outputs = {output.output_type: output.output_id for output in completed.outputs}
        return WorkflowSetup(
            services=ai_services,
            application_id=ingested.application_id,
            snapshot_id=ingested.job_snapshot_id,
            analysis_id=outputs["job_analysis"],
            selection_plan_id=outputs["selection_plan"],
        )

    return build


@pytest.fixture
def drafted_application(analyzed_application):
    def build(
        company: str,
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = analyzed_application(company, role, job_text)
        assert setup.analysis_id is not None
        assert setup.selection_plan_id is not None
        drafted = setup.services.drafts.draft(
            DraftCommand(
                application_id=setup.application_id,
                job_analysis_id=setup.analysis_id,
                selection_plan_id=setup.selection_plan_id,
            )
        )
        paths = working_draft_paths(setup.services, setup.application_id)
        return replace(
            setup,
            markdown=paths.markdown,
            manifest=paths.manifest,
            draft_report=drafted.validation,
        )

    return build


@pytest.fixture
def approved_application(drafted_application):
    def build(
        company: str = "Ready Co",
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = drafted_application(company, role, job_text)
        approved = approve_active_draft(setup.services, setup.application_id)
        return replace(setup, approved=approved)

    return build


@pytest.fixture
def artifact_approved_application(services: Services):
    def build(
        company: str = "Ready Co",
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        ingested = services.applications.ingest(
            IngestCommand(
                company=company,
                target_role=role,
                job_text=job_text,
                acknowledged_duplicates=True,
                client="web",
            )
        )
        activated = seed_existing_analysis(services, ingested)
        drafted = services.drafts.draft(
            DraftCommand(
                application_id=ingested.application_id,
                job_analysis_id=activated.analysis_id,
                selection_plan_id=activated.selection_plan_id,
            )
        )
        paths = working_draft_paths(services, ingested.application_id)
        approved = approve_active_draft(services, ingested.application_id)
        return WorkflowSetup(
            services=services,
            application_id=ingested.application_id,
            snapshot_id=ingested.job_snapshot_id,
            analysis_id=activated.analysis_id,
            selection_plan_id=activated.selection_plan_id,
            markdown=paths.markdown,
            manifest=paths.manifest,
            draft_report=drafted.validation,
            approved=approved,
        )

    return build


@pytest.fixture
def ready_application(
    approved_application,
    deterministic_renderer,
    transaction_manager: SqlAlchemyTransactionManager,
    artifact_catalog: SqlAlchemyArtifactCatalog,
    application_store: SqlAlchemyApplicationStore,
):
    def build(
        company: str = "Ready Co",
        role: str = "Account Manager",
        job_text: str = ACCOUNT_MANAGER_JOB,
    ) -> WorkflowSetup:
        setup = approved_application(company, role, job_text)
        rendered = setup.services.rendering.render(setup.application_id)
        with transaction_manager.read() as tx:
            pdf_record = artifact_catalog.latest_artifact_version(
                tx, setup.application_id, "resume_pdf"
            )
            current_status = application_store.get_application(tx, setup.application_id)[
                "current_status"
            ]
        pdf = artifact_path(setup.services, pdf_record["path"])
        assert rendered.validation.passed, rendered.validation.model_dump()
        assert current_status == "saved"
        assert setup.services.rendering.ready_qualification(setup.application_id).ready_qualified
        return replace(setup, pdf=pdf, ready_report=rendered.validation)

    return build
