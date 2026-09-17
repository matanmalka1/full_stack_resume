from __future__ import annotations

from pathlib import Path

from cv_engine.application.commands import AnalyzeCommand, ApproveDraftCommand, ValidateDraftCommand
from cv_engine.application.services.analysis import PreparedAnalysis
from cv_engine.application.services.analysis_selection import AnalysisSelection
from cv_engine.domain.contracts.analysis import JobAnalysis
from cv_engine.domain.contracts.analysis_proposal import AnalysisProposal
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track
from cv_engine.domain.draft_markdown import parse_draft
from cv_engine.infrastructure.artifacts import FilesystemArtifactStore
from cv_engine.runtime.composition import Services
from cv_engine.runtime.paths import AppPaths


def artifact_store(root: Path) -> FilesystemArtifactStore:
    """The real artifact adapter for a test project.

    Tests that need a draft on disk go through the same adapter the product
    uses, so no test carries its own copy of the storage layout.
    """
    return FilesystemArtifactStore(AppPaths.from_root(root))


def store_draft(root: Path, draft):
    """Write a working draft and return its Markdown path and exact text."""
    stored = artifact_store(root).write_working_draft(draft)
    return stored.paths.markdown, stored.markdown


def seed_existing_analysis(
    services: Services,
    ingested,
    *,
    activation_command: AnalyzeCommand | None = None,
    **overrides,
):
    """Persist an already-existing analysis for downstream tests without invoking AI."""
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
            job_snapshot_id=ingested.job_snapshot_id,
        ),
        PreparedAnalysis(
            result=analysis,
            plan_manifest=AnalysisSelection.manifest(analysis, knowledge),
            provider="test",
            model="existing-analysis-fixture",
            candidate_context_version=knowledge.candidate.context_version,
            candidate_context_hash=knowledge.candidate.version_hash,
            profile_version=knowledge.profiles.version,
            selection_policy_version=knowledge.policies.version,
            track_emphasis_dependencies={
                "track": analysis.track.value,
                "emphasis": analysis.emphasis.value,
            },
            normalized_role=profile.normalized_role,
        ),
    )


def seed_analysis_for_command(services: Services, command: AnalyzeCommand, **analysis_values):
    """Seed an existing analysis explicitly for a downstream test scenario."""
    services.analysis.snapshot_source(command.application_id, command.job_snapshot_id)
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


def script_analysis(fake_openai, **overrides) -> AnalysisProposal:
    """Script the single analysis call and return what was scripted."""
    proposal = analysis_proposal(**overrides)
    fake_openai.script("propose_analysis", proposal)
    return proposal


def validate_active_draft(services: Services, application_id: str):
    """Validate the Application's active draft and return the run result.

    The v2 command takes a WorkingDraft ID and an exact edit version, so
    resolving "the active one" is the caller's job. Every test that used to
    call `validate_working(application_id)` resolves it the same way here
    rather than each writing its own two lines.
    """
    working = services.repository.active_working_draft(application_id)
    return services.drafts.validate_draft(
        ValidateDraftCommand(
            working_draft_id=working.id,
            expected_edit_version=working.edit_version,
        )
    )


def approve_active_draft(services: Services, application_id: str, *, revision_id=None):
    """Validate, then approve exactly what that run passed.

    Approval no longer validates for itself, so a caller must obtain the exact
    run first. Keeping that sequence in one helper prevents tests from quietly
    bypassing the binding the product requires.
    """
    validated = validate_active_draft(services, application_id)
    return services.drafts.approve_draft(
        ApproveDraftCommand(
            working_draft_id=validated.working_draft_id,
            expected_edit_version=validated.edit_version,
            validation_run_id=validated.validation_run_id,
            client="web",
        ),
        revision_id=revision_id,
    )


def working_claim(services: Services, application_id: str, fact_id: str):
    manifest = services.artifacts.working_paths(application_id).manifest
    draft = parse_draft(manifest.read_text(encoding="utf-8"))
    return next(
        claim for section in draft.sections for claim in section.claims if fact_id in claim.fact_ids
    )


def exact_fact_claim(draft, fact_ids: list[str]):
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.fact_ids == fact_ids
    )


def claim_by_id(draft, claim_id: str):
    return next(
        claim
        for section in draft.sections
        for claim in section.claims
        if claim.claim_id == claim_id
    )


def artifact_version_and_path(
    services: Services,
    application_id: str,
    artifact_type: str,
    lifecycle_status: str,
):
    version = services.repository.latest_artifact_version(
        application_id, artifact_type, lifecycle_status
    )
    return version, services.artifacts.resolve(version["path"])


def passing_migration_test_runner(root: Path) -> Path:
    return root / "data/migration/migration-tests.json"
