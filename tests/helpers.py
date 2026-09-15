from __future__ import annotations

from pathlib import Path

from cv_engine.application.commands import AnalyzeCommand, ApproveDraftCommand, ValidateDraftCommand
from cv_engine.application.services.analysis import PreparedAnalysis
from cv_engine.application.services.analysis_selection import AnalysisSelection
from cv_engine.domain.analysis.requirements.concepts import RequirementConceptStore
from cv_engine.domain.analysis.requirements.segmentation import requirement_lines
from cv_engine.domain.contracts.analysis import JobAnalysis, UnmappedStatement
from cv_engine.domain.contracts.providers import RequirementExtractionProposal
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


def seed_existing_analysis(services: Services, ingested, **overrides):
    """Persist an already-existing analysis for downstream tests without invoking AI."""
    knowledge = services.analysis.load_knowledge()
    profile_name = ProfileName(overrides.pop("profile_override", "account-manager"))
    profile = knowledge.profiles.get(profile_name)
    analysis = JobAnalysis(
        analysis_version="2.0",
        track=Track(overrides.pop("track_override", profile.track)),
        profile=profile_name,
        emphasis=Emphasis(overrides.pop("emphasis_override", profile.default_emphasis)),
        language=overrides.pop("language_override", "en"),
        confidence=0.99,
        rationale="existing analysis test fixture",
        fit="high",
        fit_score=1.0,
        gaps=[],
        requirements=[],
        extraction_version="test-ai-v1",
        unmapped_statements=[],
        understanding={"by_ai": 0},
        interpretation_decisions=[],
        mandatory_requirements=[],
        preferred_requirements=[],
        keywords=[],
        **overrides,
    )
    return services.analysis.activate(
        AnalyzeCommand(
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


ACCOUNT_MANAGER_JOB = (
    "Account Manager responsible for retention, portfolio growth, negotiation, "
    "and customer relationships.\n\n"
    "Requirements:\n"
    "- Experience owning the full sales cycle.\n"
    "- Fluent English."
)

# Hebrew, low confidence, one hard gap and one warning gap: the deterministic
# classifier requires approval here, so it exposes anything a provider could
# quietly relax.
AMBIGUOUS_HEBREW_JOB = (
    "דרוש מנהל לקוחות עם ניסיון בפיתוח עסקי ובניהול תיק לקוחות מול ארגונים גדולים. "
    "התפקיד כולל אחריות על שימור, גיוס לקוחות חדשים והובלת תהליכי מכירה מורכבים. "
    "דרישות: account manager, business development, Salesforce, must have direct saas sales."
)

# A readable review-path posting: classification confidence still requires an
# explicit Profile decision, while the technology-company requirement remains
# a separate hard gap that the user must accept by its requirement ID.
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


def trivial_requirement_extraction(
    job_text: str, concepts: RequirementConceptStore
) -> RequirementExtractionProposal:
    """A `propose_requirement_extraction` answer that passes both gates and never
    reports a failed extraction, for tests whose subject is something else -
    classification merge behaviour, retry policy, provenance - and that only
    need the AI analysis pipeline (stage-1 plan §3.7) to get past the
    extraction step without asserting anything about what it extracted.

    Every requirement-bearing statement in `job_text` is declared as an
    `unmapped_statements` entry rather than left silently uncovered, so the
    stub discloses what it did not read instead of hiding it. That is all it
    does: declaring a statement unmapped explains an omission and does not
    read it, so an analysis built on this carries `extraction-failed` and a
    zero extraction confidence, exactly as a posting nothing read should. No
    requirement is proposed, so it never asserts a false `matched` either.

    It is a stub for "the extraction step ran and returned something valid" -
    not a stand-in for a content-bearing extraction. A test asserting on
    requirements, coverage, confidence, or Fit must script its own proposal.
    """
    return RequirementExtractionProposal(
        requirements=[],
        unmapped_statements=[
            UnmappedStatement(
                start=line.start,
                end=line.end,
                text=line.text,
                source_role="other",
                reason="test fixture: not extracted, declared to keep completeness honest",
            )
            for line in requirement_lines(job_text, concepts)
        ],
    )


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
