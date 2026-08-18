"""An AI classification proposal may not decide deterministic policy.

`AnalysisService.analyze` used to build its authoritative `JobAnalysis` from the provider
response and merge only hard gaps back, so a provider could raise confidence,
switch the document language, clear `classification_requires_approval`, and erase
deterministic warning gaps. These tests pin the policy that replaced it.
"""

from __future__ import annotations

import pytest

from cv_engine.application.commands import DraftCommand
from cv_engine.domain.analysis.approval import merge_classification
from cv_engine.domain.analysis.classification import classify_job
from cv_engine.domain.models import Emphasis, FitLevel, Gap, ProfileName, Track
from cv_engine.domain.profiles import ProfileStore
from cv_engine.application.errors import WorkflowError
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB


def test_provider_cannot_relax_approval_confidence_or_language(
    provider_analysis, classification_proposal
) -> None:
    deterministic = classify_job(AMBIGUOUS_HEBREW_JOB)
    assert deterministic.classification_requires_approval
    assert deterministic.language == "he"

    # The job's hard gap is accepted, so the approval gate is what must block.
    setup = provider_analysis(classification_proposal(), accept_low_fit=True)
    services, application_id, analysis = setup

    assert analysis.classification_requires_approval
    assert analysis.language == "he"
    assert analysis.confidence == deterministic.confidence
    with pytest.raises(WorkflowError, match="ambiguous classification"):
        services.drafts.draft(
            DraftCommand(
                application_id=application_id,
                job_analysis_id=setup.analysis_id,
                selection_plan_id=setup.services.repository.latest_selection_plan(
                    application_id
                ).id,
            )
        )

    _, stored = services.repository.latest_analysis(application_id)
    assert stored == analysis
    assert services.repository.get_application(application_id)["language"] == "he"


def test_explicit_user_override_beats_the_provider(
    provider_analysis, classification_proposal
) -> None:
    _, _, analysis = provider_analysis(
        classification_proposal(
            track=Track.DEVELOPMENT,
            profile=ProfileName.DEVELOPMENT,
            emphasis=Emphasis.DEVELOPMENT_AI,
        ),
        job_text=ACCOUNT_MANAGER_JOB,
        track="tech-sales",
        profile="pre-sales-solutions-consultant",
        emphasis="tech-consultative-sales",
        language="he",
    )

    assert analysis.track is Track.TECH_SALES
    assert analysis.profile is ProfileName.PRE_SALES
    assert analysis.emphasis is Emphasis.TECH_CONSULTATIVE
    assert analysis.language == "he"


def test_deterministic_gaps_survive_and_may_only_be_hardened(
    profile_store: ProfileStore, classification_proposal
) -> None:
    deterministic = classify_job(AMBIGUOUS_HEBREW_JOB)
    salesforce = next(gap for gap in deterministic.gaps if gap.requirement == "Salesforce")
    assert salesforce.severity == "warning"

    silent = merge_classification(deterministic, classification_proposal(gaps=[]), profile_store)
    hardened = merge_classification(
        deterministic,
        classification_proposal(
            gaps=[Gap(requirement="Salesforce", severity="hard", reason="provider reason")]
        ),
        profile_store,
    )

    assert silent.gaps == deterministic.gaps
    assert "Salesforce" in silent.preferred_requirements
    hardened_gap = next(gap for gap in hardened.gaps if gap.requirement == "Salesforce")
    assert hardened_gap.severity == "hard"
    assert hardened_gap.reason == salesforce.reason
    assert hardened_gap.substitute_fact_ids == salesforce.substitute_fact_ids


def test_fit_is_derived_from_merged_gaps_and_never_improved(
    profile_store: ProfileStore, classification_proposal
) -> None:
    clean = classify_job(ACCOUNT_MANAGER_JOB)
    assert clean.fit is FitLevel.HIGH and clean.gaps == []

    added = merge_classification(
        clean,
        classification_proposal(
            gaps=[Gap(requirement="German", severity="hard", reason="not verified")]
        ),
        profile_store,
    )
    assert added.fit is FitLevel.LOW
    assert added.mandatory_requirements == ["German"]

    low = classify_job(AMBIGUOUS_HEBREW_JOB)
    assert low.fit is FitLevel.LOW
    assert merge_classification(low, classification_proposal(), profile_store).fit is FitLevel.LOW


def test_emphasis_disagreement_is_an_approval_gate(
    profile_store: ProfileStore, classification_proposal
) -> None:
    """Emphasis selects content, so disagreeing about it materially changes the CV.

    This inverts the earlier rule. Emphasis used to be inert metadata — the draft
    was identical whichever one won — so a disagreement was safe to apply
    silently. Now it drives fact selection, which puts it under the same §9.4
    routing as Track and Profile: two classifiers disagreeing means neither is
    authoritative, and only an Emphasis override settles it.
    """
    deterministic = classify_job("Account Executive closing quota new business")
    assert not deterministic.classification_requires_approval
    assert deterministic.emphasis is Emphasis.NEW_BUSINESS

    moved = merge_classification(
        deterministic,
        classification_proposal(
            track=deterministic.track,
            profile=deterministic.profile,
            emphasis=Emphasis.TECH_CONSULTATIVE,
        ),
        profile_store,
    )
    # An emphasis the Profile does not allow used to reach build_draft and raise
    # there, after the analysis had already been written to SQLite.
    disallowed = merge_classification(
        deterministic,
        classification_proposal(
            track=deterministic.track,
            profile=deterministic.profile,
            emphasis=Emphasis.DEVELOPMENT_AI,
        ),
        profile_store,
    )

    assert moved.emphasis is Emphasis.TECH_CONSULTATIVE
    assert moved.approval_reasons == ["emphasis-disagreement"]
    assert moved.classification_requires_approval

    # Falling back to the deterministic Emphasis is agreement, not disagreement.
    assert disallowed.emphasis in profile_store.get(disallowed.profile).allowed_emphases
    assert "emphasis-disagreement" not in disallowed.approval_reasons

    # Only an Emphasis override answers it; a Profile override does not.
    settled = merge_classification(
        classify_job(
            "Account Executive closing quota new business",
            emphasis_override="tech-consultative-sales",
        ),
        classification_proposal(
            track=deterministic.track,
            profile=deterministic.profile,
            emphasis=Emphasis.NEW_BUSINESS,
        ),
        profile_store,
    )
    assert not settled.classification_requires_approval


def test_inconsistent_proposal_is_rejected_rather_than_applied(
    profile_store: ProfileStore, classification_proposal
) -> None:
    deterministic = classify_job(ACCOUNT_MANAGER_JOB)

    merged = merge_classification(
        deterministic,
        classification_proposal(track=Track.DEVELOPMENT, profile=ProfileName.ACCOUNT_MANAGER),
        profile_store,
    )

    assert (merged.track, merged.profile) == (deterministic.track, deterministic.profile)
    assert merged.classification_requires_approval
    assert "was not applied" in merged.rationale


def test_deterministic_ambiguity_is_resolved_by_choosing_the_classification() -> None:
    ambiguous = classify_job(AMBIGUOUS_HEBREW_JOB)
    assert ambiguous.approval_reasons == ["ambiguous-signals", "low-confidence"]
    assert ambiguous.classification_requires_approval

    # The reasons stay on the record; the override is what marks them answered.
    resolved = classify_job(AMBIGUOUS_HEBREW_JOB, track_override="sales")
    assert resolved.approval_reasons == ambiguous.approval_reasons
    assert not resolved.classification_requires_approval

    unrelated = classify_job(AMBIGUOUS_HEBREW_JOB, emphasis_override="balanced-sales")
    assert unrelated.classification_requires_approval
