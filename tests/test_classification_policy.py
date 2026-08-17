"""An AI classification proposal may not decide deterministic policy.

`Engine.analyze` used to build its authoritative `JobAnalysis` from the provider
response and merge only hard gaps back, so a provider could raise confidence,
switch the document language, clear `classification_requires_approval`, and erase
deterministic warning gaps. These tests pin the policy that replaced it.
"""

from __future__ import annotations

import pytest

from cv_engine.analysis import classify_job, merge_classification, unresolved_approval_reasons
from cv_engine.models import Emphasis, FitLevel, Gap, ProfileName, Track
from cv_engine.profiles import ProfileStore
from cv_engine.workflow import WorkflowError
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB


def test_provider_cannot_relax_approval_confidence_or_language(
    provider_analysis, classification_proposal
) -> None:
    deterministic = classify_job(AMBIGUOUS_HEBREW_JOB)
    assert deterministic.classification_requires_approval
    assert deterministic.language == "he"

    # The job's hard gap is accepted, so the approval gate is what must block.
    engine, application_id, analysis = provider_analysis(
        classification_proposal(), accept_low_fit=True
    )

    assert analysis.classification_requires_approval
    assert analysis.language == "he"
    assert analysis.confidence == deterministic.confidence
    with pytest.raises(WorkflowError, match="ambiguous classification"):
        engine.draft(application_id)

    _, stored = engine.repo.latest_analysis(application_id)
    assert stored == analysis
    assert engine.repo.get_application(application_id)["language"] == "he"


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


def test_confidence_can_only_be_lowered_and_both_sources_are_recorded(
    profile_store: ProfileStore, classification_proposal
) -> None:
    deterministic = classify_job(AMBIGUOUS_HEBREW_JOB)

    raised = merge_classification(deterministic, classification_proposal(confidence=0.99), profile_store)
    lowered = merge_classification(deterministic, classification_proposal(confidence=0.10), profile_store)

    assert raised.confidence == deterministic.confidence
    assert raised.deterministic_confidence == deterministic.confidence
    assert raised.proposal_confidence == 0.99
    assert lowered.confidence == 0.10


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
        classification_proposal(gaps=[Gap(requirement="German", severity="hard", reason="not verified")]),
        profile_store,
    )
    assert added.fit is FitLevel.LOW
    assert added.mandatory_requirements == ["German"]

    low = classify_job(AMBIGUOUS_HEBREW_JOB)
    assert low.fit is FitLevel.LOW
    assert merge_classification(low, classification_proposal(), profile_store).fit is FitLevel.LOW


def test_track_or_profile_disagreement_requires_approval(
    profile_store: ProfileStore, classification_proposal
) -> None:
    deterministic = classify_job(ACCOUNT_MANAGER_JOB)
    assert not deterministic.classification_requires_approval

    merged = merge_classification(
        deterministic,
        classification_proposal(
            track=Track.TECH_SALES,
            profile=ProfileName.PRE_SALES,
            emphasis=Emphasis.TECH_CONSULTATIVE,
        ),
        profile_store,
    )

    assert (merged.track, merged.profile) == (Track.TECH_SALES, ProfileName.PRE_SALES)
    assert merged.classification_requires_approval


def test_emphasis_is_a_refinement_not_an_approval_gate(
    profile_store: ProfileStore, classification_proposal
) -> None:
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
    assert not moved.classification_requires_approval
    assert disallowed.emphasis in profile_store.get(disallowed.profile).allowed_emphases


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


def test_an_unrelated_override_does_not_open_the_classification_gate(
    provider_analysis, classification_proposal
) -> None:
    """Emphasis and language say nothing about a Track/Profile disagreement."""
    engine, application_id, analysis = provider_analysis(
        classification_proposal(
            track=Track.TECH_SALES,
            profile=ProfileName.PRE_SALES,
            emphasis=Emphasis.TECH_CONSULTATIVE,
        ),
        job_text=ACCOUNT_MANAGER_JOB,
        emphasis="balanced-sales",
        language="he",
    )

    assert "profile-disagreement" in analysis.approval_reasons
    assert analysis.classification_requires_approval
    with pytest.raises(WorkflowError, match="profile-disagreement"):
        engine.draft(application_id)

    _, stored = engine.repo.latest_analysis(application_id)
    assert stored.approval_reasons == analysis.approval_reasons
    assert stored.user_override == {"emphasis": "balanced-sales", "language": "he"}


def test_only_the_override_that_answers_the_ambiguity_resolves_it(
    profile_store: ProfileStore, classification_proposal
) -> None:
    proposal = classification_proposal(
        track=Track.TECH_SALES,
        profile=ProfileName.PRE_SALES,
        emphasis=Emphasis.TECH_CONSULTATIVE,
    )

    # A Track override leaves the Profile inside that Track undecided; choosing a
    # Profile determines its Track, so it settles the pair.
    track_only = merge_classification(
        classify_job(ACCOUNT_MANAGER_JOB, track_override="tech-sales"), proposal, profile_store
    )
    profile_chosen = merge_classification(
        classify_job(ACCOUNT_MANAGER_JOB, profile_override="tech-sales"), proposal, profile_store
    )

    assert "profile-disagreement" in track_only.approval_reasons
    assert track_only.classification_requires_approval
    assert "profile-disagreement" in profile_chosen.approval_reasons
    assert not profile_chosen.classification_requires_approval
    assert profile_chosen.profile is ProfileName.TECH_SALES


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


def test_an_analysis_recorded_before_reasons_existed_fails_closed() -> None:
    legacy = classify_job(ACCOUNT_MANAGER_JOB).model_copy(update={
        "classification_requires_approval": True,
        "approval_reasons": [],
        "user_override": {"emphasis": "balanced-sales"},
    })

    assert unresolved_approval_reasons(legacy) == ["unspecified-ambiguity"]
    assert unresolved_approval_reasons(
        legacy.model_copy(update={"user_override": {"profile": "account-manager"}})
    ) == []


def test_proposal_fields_the_provider_owns_still_reach_the_analysis(
    profile_store: ProfileStore, classification_proposal
) -> None:
    deterministic = classify_job(ACCOUNT_MANAGER_JOB)

    merged = merge_classification(
        deterministic,
        classification_proposal(keywords=["renewal forecasting"]),
        profile_store,
    )

    assert merged.rationale == "provider rationale"
    assert "renewal forecasting" in merged.keywords
    assert set(deterministic.keywords) <= set(merged.keywords)
