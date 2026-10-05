from __future__ import annotations

from pathlib import Path
from typing import cast

from sqlalchemy import func, select

from cv_engine.application.commands import (
    AnalyzeCommand,
    ApproveDocumentCommand,
    CheckDocumentCommand,
    IngestCommand,
)
from cv_engine.application.ports.documents import DocumentBody
from cv_engine.application.services.analysis.preparation import PreparedAnalysis
from cv_engine.application.services.documents import built_with, compose_content
from cv_engine.domain.contracts.analysis import JobAnalysis
from cv_engine.domain.contracts.analysis_proposal import AnalysisProposal
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track
from cv_engine.domain.drafts import seal_draft
from cv_engine.infrastructure.persistence.connection import SqlAlchemyTransactionManager
from cv_engine.infrastructure.persistence.documents import (
    SqlAlchemyDocumentStore,
    SqlAlchemyDocumentSubmissionStore,
)
from cv_engine.infrastructure.persistence.tables import metadata
from cv_engine.runtime.composition import Services
from cv_engine.util import utc_now


def store_draft(root: Path, draft):
    """Seal a draft, write its Markdown under `root`, and return the path and exact text."""
    sealed, markdown, _manifest = seal_draft(draft)
    path = root / "drafts" / sealed.application_id / "resume.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path, markdown


def artifact_path(services: Services, stored_path: str) -> Path:
    """Resolve a trusted stored reference so an integrity test can mutate its bytes."""
    return services.paths.root / stored_path


def artifact_reference(services: Services, path: Path) -> str:
    """Create the project-relative reference used by a synthetic artifact row."""
    return services.paths.relative(path)


def seed_existing_analysis(
    services: Services,
    ingested,
    *,
    activation_command: AnalyzeCommand | None = None,
    **overrides,
):
    """Persist an already-existing analysis for downstream tests without invoking AI.

    The first analysis of an Application also creates its CV document, pinned to it
    with no content (§13).
    """
    knowledge = services.analysis.load_knowledge()
    profile_name = ProfileName(overrides.pop("profile_override", "account-manager"))
    profile = knowledge.profiles.get(profile_name)
    requirements = overrides.pop("requirements", [])
    analysis = JobAnalysis(
        track=Track(overrides.pop("track_override", None) or profile.track),
        profile=profile_name,
        emphasis=Emphasis(overrides.pop("emphasis_override", None) or profile.default_emphasis),
        language=overrides.pop("language_override", None) or "en",
        summary=overrides.pop("summary", "existing analysis test fixture"),
        keywords=overrides.pop("keywords", []),
        requirements=requirements,
        **overrides,
    )
    return services.analysis.activate(
        activation_command
        or AnalyzeCommand(
            application_id=ingested.application_id,
            job_text_hash=ingested.job_text_hash,
        ),
        PreparedAnalysis(
            result=analysis,
            built_with=built_with(knowledge),
            provider="test",
            model="existing-analysis-fixture",
            normalized_role=profile.normalized_role,
        ),
    )


def seed_analysis_for_command(services: Services, command: AnalyzeCommand, **analysis_values):
    """Seed an existing analysis explicitly for a downstream test scenario."""
    services.analysis.job_text_source(command.application_id, command.job_text_hash)
    return seed_existing_analysis(
        services,
        command,
        activation_command=command,
        track_override=command.track_override,
        profile_override=command.profile_override or "account-manager",
        emphasis_override=command.emphasis_override,
        language_override=command.language_override or "en",
        **analysis_values,
    )


ACCOUNT_MANAGER_JOB = (
    "Account Manager responsible for retention, portfolio growth, negotiation, "
    "and customer relationships.\n\n"
    "Requirements:\n"
    "- Experience owning the full sales cycle.\n"
    "- Fluent English."
)

# An ambiguous Hebrew posting for review-flow scenarios.
AMBIGUOUS_HEBREW_JOB = (
    "דרוש מנהל לקוחות עם ניסיון בפיתוח עסקי ובניהול תיק לקוחות מול ארגונים גדולים. "
    "התפקיד כולל אחריות על שימור, גיוס לקוחות חדשים והובלת תהליכי מכירה מורכבים. "
    "דרישות: account manager, business development, Salesforce, must have direct saas sales."
)

# A readable review-path posting with a technology-company requirement.
REVIEW_DECISION_JOB = (
    "Account manager and business development role for enterprise customers.\n"
    "התפקיד כולל אחריות על שימור, גיוס לקוחות חדשים והובלת תהליכי מכירה מורכבים.\n\n"
    "Requirements:\n"
    "- Experience owning the full sales cycle.\n"
    "- Sales experience at a SaaS company."
)

PAYME_TECH_SALES_JOB = (
    "FinTech platform for small businesses. Strategic Partnerships Sales Manager "
    "responsible for new partner acquisition and outbound Sales to website builders, "
    "CRMs, marketplaces, and software providers that can embed financial products. "
    "Engage prospects by phone and email, understand their needs, offer tailored "
    "solutions, pitch the service, guide the Sales process through closing, onboard "
    "customers, and maintain Sales progress and follow-up tasks in our CRM system. "
    "Prefer inside Sales experience in a SaaS or tech-related industry."
)


def analysis_proposal(**overrides) -> AnalysisProposal:
    """One `propose_analysis` answer, for tests whose subject is something else.

    The default proposes no requirements at all: a stub for "the analysis step
    ran and returned something valid", not a stand-in for a content-bearing
    reading. An analysis built on it carries no coverage and no Fit, which is
    what a posting nothing read should produce, and it asserts no false
    `matched` on the way.

    A test asserting on requirements, coverage, or Fit passes its own
    `requirements=[...]`. One factory rather than one per call site, because
    there is one call to script.
    """
    return AnalysisProposal(
        **{
            "track": Track.SALES,
            "profile": ProfileName.ACCOUNT_MANAGER,
            "emphasis": Emphasis.ACCOUNT_GROWTH,
            "language": "en",
            "summary": "test fixture reading",
            "requirements": [],
            "keywords": [],
            **overrides,
        }
    )


def services_transactions(services: Services) -> SqlAlchemyTransactionManager:
    """The transaction manager `services` was composed with, on its own engine.

    Building a fresh engine from `services.database_url` per call opened a pool
    that was never disposed; every caller wants the one already composed.
    """
    return cast(SqlAlchemyTransactionManager, services.operation_runner.transactions)


def stored_document(services: Services, application_id: str):
    transactions = services_transactions(services)
    with transactions.read() as tx:
        document = SqlAlchemyDocumentStore(transactions).document(tx, application_id)
    assert document is not None
    return document


def seed_document(
    services: Services,
    company="Document Co",
    *,
    role="Account Manager",
    job_text=ACCOUNT_MANAGER_JOB,
    **analysis_values,
):
    ingested = services.applications.ingest(
        IngestCommand(
            company=company,
            target_role=role,
            job_text=job_text,
            acknowledged_duplicates=True,
            client="web",
        )
    )
    return ingested, seed_existing_analysis(services, ingested, **analysis_values)


def composed_content(services: Services, application_id: str, chosen=None):
    """The document's content in canonical wording.

    With no `chosen`, the frame `create_draft` hands the provider: every section's
    whole pool. With `chosen` (section English name -> fact IDs), what the engine lays
    out once a writer kept those facts.
    """
    source = services.drafts.document_source(application_id)
    document = source.document
    return compose_content(
        application_id,
        document.analysis_id,
        source.job_text_hash,
        source.analysis,
        services.drafts.load_knowledge(),
        chosen,
    )


def seed_draft(services: Services, application_id: str, chosen=None):
    """Persist existing content for downstream tests without invoking AI.

    The content is canonical wording: the whole frame, as a `draft_resume` that kept
    and echoed every claim (`fake_provider.echo_draft`) leaves it, or the `chosen`
    facts laid out.
    """
    content = composed_content(services, application_id, chosen)
    document = stored_document(services, application_id)
    transactions = services_transactions(services)
    with transactions.write() as tx:
        return SqlAlchemyDocumentStore(transactions).update_body(
            tx,
            application_id,
            document.document_hash,
            DocumentBody(analysis_id=document.analysis_id, content=content),
            updated_at=utc_now(),
        )


def validate_active_draft(services: Services, application_id: str):
    document = stored_document(services, application_id)
    return services.draft_review.check_document(
        CheckDocumentCommand(
            application_id=application_id,
            expected_document_hash=document.document_hash,
        )
    )


def approve_active_draft(services: Services, application_id: str):
    document = stored_document(services, application_id)
    return services.draft_review.approve_document(
        ApproveDocumentCommand(
            application_id=application_id,
            expected_document_hash=document.document_hash,
            client="web",
        )
    )


def working_claim(services: Services, application_id: str, fact_id: str):
    document = stored_document(services, application_id)
    assert document.content is not None
    return next(
        claim
        for section in document.content.sections
        for claim in section.claims
        if fact_id in claim.fact_ids
    )


def claim_by_id(draft, claim_id: str):
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.claim_id == claim_id
    )


def persisted_counts(database_engine) -> dict[str, int]:
    """Row counts for every product table, discovered rather than listed.

    A rejected command must leave nothing behind anywhere, so this counts the whole
    database instead of a remembered set of tables filtered by application_id. That
    covers indirect records with no application_id column of their own — Operation
    outputs, AI calls, fact events — and, more importantly, covers the
    next table automatically: a list would have gone on passing while a new table
    quietly gained a row.
    """
    with database_engine.connect() as connection:
        return {
            table.name: connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in metadata.sorted_tables
        }


def stored_submissions(services: Services, application_id: str):
    transactions = services_transactions(services)
    with transactions.read() as tx:
        return SqlAlchemyDocumentSubmissionStore(transactions).submissions(tx, application_id)


def edit_document_claim(
    services: Services, application_id: str, claim_id: str, fact_ids: list[str], *, text: str
):
    from cv_engine.application.commands import ClaimPatch, UpdateDocumentCommand

    return services.draft_editing.update_document(
        UpdateDocumentCommand(
            application_id=application_id,
            expected_document_hash=stored_document(services, application_id).document_hash,
            claim_edits=[ClaimPatch(claim_id=claim_id, fact_ids=fact_ids, text=text)],
        )
    )
