"""An AI classification proposal may not decide deterministic policy.

`AnalysisService.analyze` used to build its authoritative `JobAnalysis` from the provider
response and merge only hard gaps back, so a provider could raise confidence,
switch the document language, clear `classification_requires_approval`, and erase
deterministic warning gaps. These tests pin the policy that replaced it.
"""

from __future__ import annotations

import pytest
from helpers import ACCOUNT_MANAGER_JOB, AMBIGUOUS_HEBREW_JOB

from cv_engine.application.commands import AnalyzeCommand, DraftCommand, IngestCommand
from cv_engine.application.errors import WorkflowError
from cv_engine.domain.analysis.approval import (
    ANALYSIS_INCOMPLETE,
    APPROVAL_REASONS,
    merge_classification,
    unresolved_approval_reasons,
)
from cv_engine.domain.contracts.analysis import RequirementAttestation, RequirementInterpretation
from cv_engine.domain.contracts.providers import ProposedRequirement, RequirementExtractionProposal
from cv_engine.domain.models import Emphasis, FitLevel, Gap, ProfileName, Track
from cv_engine.domain.profiles import ProfileStore


def test_provider_cannot_relax_approval_confidence_or_language(
    provider_analysis, classification_proposal, classify, fake_openai
) -> None:
    deterministic = classify(AMBIGUOUS_HEBREW_JOB)
    assert deterministic.classification_requires_approval
    assert deterministic.language == "he"

    # This test's subject is classification-merge policy, not extraction, so
    # the extraction answer must not itself block drafting: unlike
    # `trivial_requirement_extraction`, it reads the "Salesforce" quote (a
    # non-mandatory match, so it cannot also open `coverage-undetermined`) so
    # `extraction-failed` never joins `analysis.approval_reasons` and the
    # classification-ambiguity gate is the one left to block the draft.
    quote = "Salesforce"
    start = AMBIGUOUS_HEBREW_JOB.index(quote)
    fake_openai.script(
        "propose_requirement_extraction",
        RequirementExtractionProposal(
            requirements=[
                ProposedRequirement(
                    attestation=RequirementAttestation(
                        quote=quote, start=start, end=start + len(quote)
                    ),
                    interpretation=RequirementInterpretation(
                        source_role="requirement",
                        obligation="preferred",
                        composition="single",
                        negation=False,
                    ),
                    kind="presence",
                    label=quote,
                )
            ],
            unmapped_statements=[],
        ),
    )

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
    profile_store: ProfileStore, classification_proposal, classify
) -> None:
    deterministic = classify(AMBIGUOUS_HEBREW_JOB)
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
    profile_store: ProfileStore, classification_proposal, classify
) -> None:
    # The posting has to actually state a requirement the engine reads. An
    # empty requirement list is no longer HIGH - it reports `requirements-absent`
    # and no score at all, because "nothing demanded" and "nothing recognised"
    # are not distinguishable from the list alone.
    clean = classify(
        "Account Manager responsible for retention, portfolio growth, negotiation, "
        "and customer relationships.\n\nRequirements:\n"
        "- 3+ years of sales closing experience.\n"
    )
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

    low = classify(AMBIGUOUS_HEBREW_JOB)
    assert low.fit is FitLevel.LOW
    assert merge_classification(low, classification_proposal(), profile_store).fit is FitLevel.LOW


#: Account Executive vocabulary *and* one requirement statement the concept
#: vocabulary reads, so a test about a classification gate is not also testing
#: `requirements-absent`.
READ_ACCOUNT_EXECUTIVE_POSTING = (
    "Account Executive closing quota new business.\n\n"
    "Requirements:\n- Native English is required.\n"
)


def test_emphasis_disagreement_is_an_approval_gate(
    profile_store: ProfileStore, classification_proposal, classify
) -> None:
    """Emphasis selects content, so disagreeing about it materially changes the CV.

    This inverts the earlier rule. Emphasis used to be inert metadata — the draft
    was identical whichever one won — so a disagreement was safe to apply
    silently. Now it drives fact selection, which puts it under the same §9.4
    routing as Track and Profile: two classifiers disagreeing means neither is
    authoritative, and only an Emphasis override settles it.
    """
    # With a requirement the engine reads, so the gate under test is Emphasis
    # disagreement rather than `requirements-absent`.
    deterministic = classify(READ_ACCOUNT_EXECUTIVE_POSTING)
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
    # there, after the analysis had already been written to the database.
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
        classify(
            READ_ACCOUNT_EXECUTIVE_POSTING,
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
    profile_store: ProfileStore, classification_proposal, classify
) -> None:
    deterministic = classify(ACCOUNT_MANAGER_JOB)

    merged = merge_classification(
        deterministic,
        classification_proposal(track=Track.DEVELOPMENT, profile=ProfileName.ACCOUNT_MANAGER),
        profile_store,
    )

    assert (merged.track, merged.profile) == (deterministic.track, deterministic.profile)
    assert merged.classification_requires_approval
    assert "was not applied" in merged.rationale


def test_deterministic_ambiguity_is_resolved_by_choosing_the_classification(classify) -> None:
    ambiguous = classify(AMBIGUOUS_HEBREW_JOB)
    # `extraction-failed` now stands on this posting: its requirement statement
    # is unread by the concept vocabulary, and the legacy gap rules matching
    # "Salesforce"/"saas" no longer clears that - they only earn the confidence
    # floor. `requirements-unmapped` names the statement itself.
    assert ambiguous.approval_reasons == [
        "extraction-failed",
        "requirements-unmapped",
        "ambiguous-signals",
        "low-confidence",
    ]
    assert ambiguous.classification_requires_approval

    # The reasons stay on the record; the override is what marks them answered -
    # the ambiguity ones. The two analysis-completeness reasons are a different
    # question, and naming a Track was never an answer to them.
    resolved = classify(AMBIGUOUS_HEBREW_JOB, track_override="sales")
    assert resolved.approval_reasons == ambiguous.approval_reasons
    assert unresolved_approval_reasons(resolved) == ["extraction-failed", "requirements-unmapped"]

    unrelated = classify(AMBIGUOUS_HEBREW_JOB, emphasis_override="balanced-sales")
    assert unrelated.classification_requires_approval
    assert "ambiguous-signals" in unresolved_approval_reasons(unrelated)


#: Requirements stated in prose that neither the concept vocabulary nor the
#: legacy gap rules read.
UNREADABLE_POSTING = (
    "Account Executive.\n"
    "You have experience closing complex B2B deals, understand enterprise "
    "procurement, and negotiate with senior stakeholders.\n"
)


def test_generation_refuses_an_unread_posting_in_its_own_terms(services) -> None:
    """The refusal must not name a decision that cannot resolve it.

    Every unresolved approval reason was refused with "requires an explicit
    Track/Profile override". For a posting the engine could not read that is
    the one thing that cannot help, and a direct API caller was told to do it -
    the same false advertisement the projection stopped making, still standing
    in the layer that enforces it.
    """
    ingested = services.applications.ingest(
        IngestCommand(
            company="Unread Generation Co",
            target_role="Account Executive",
            job_text=UNREADABLE_POSTING,
            client="web",
        )
    )
    analysed = services.analysis.analyze(
        AnalyzeCommand(
            application_id=ingested.application_id,
            job_snapshot_id=ingested.job_snapshot_id,
        )
    )
    with pytest.raises(WorkflowError) as refusal:
        services.drafts.draft(
            DraftCommand(
                application_id=ingested.application_id,
                job_analysis_id=analysed.analysis_id,
                selection_plan_id=analysed.selection_plan_id,
            )
        )
    message = str(refusal.value)
    assert "did not read this posting's requirements" in message
    assert "Track/Profile" not in message


#: States nothing this engine reads as a requirement. Not a failed extraction:
#: there was nothing to fail at.
REQUIREMENT_FREE_POSTING = (
    "Account Executive wanted for a growing team. We sell to small businesses.\n"
)

#: One requirement statement the concept vocabulary maps, one it does not.
PARTLY_MAPPED_POSTING = (
    "Account Executive.\n\n"
    "Requirements:\n"
    "- 3+ years of sales closing experience.\n"
    "- You must have exceptional gravitas in boardroom settings.\n"
)


def test_a_posting_that_states_no_requirement_reports_unknown_with_a_reason(classify) -> None:
    """`requirements-absent`, and not a fit score of 1.0.

    An empty requirement list used to score 1.0 - "nothing demanded, nothing
    missing" - which is only true if the posting really demanded nothing, and
    indistinguishable from a segmenter that read a posting full of requirements
    and recognised none of them. The score is withheld instead, and the reason
    says which of the two this is: `extraction-failed` means requirements were
    stated and none were read; this one means none were stated.
    """
    analysis = classify(REQUIREMENT_FREE_POSTING)
    assert analysis.requirements == []
    assert "requirements-absent" in analysis.approval_reasons
    assert "extraction-failed" not in analysis.approval_reasons
    assert "requirements-unmapped" not in analysis.approval_reasons
    assert analysis.fit_score is None
    assert analysis.fit is FitLevel.UNKNOWN
    assert analysis.classification_requires_approval


def test_a_requirement_statement_nothing_mapped_is_scored_and_disclosed(classify) -> None:
    """`requirements-unmapped`, and a score computed over both statements.

    The unmapped statement enters the same list `fit_score` reads, at zero
    credit, so reading one of two requirements can no longer score the same as
    reading two. `coverage-undetermined` deliberately does not fire with it: the
    synthetic entry's `mandatory` is `False` by construction, not a verified
    value, so that reason stays about requirements whose `mandatory` means
    something. `accepted-low-fit` is not what answers this either - the zero is
    arithmetic, not a judgement about the candidate.
    """
    analysis = classify(PARTLY_MAPPED_POSTING)
    assert "requirements-unmapped" in analysis.approval_reasons
    assert "requirements-absent" not in analysis.approval_reasons
    assert "extraction-failed" not in analysis.approval_reasons
    assert "coverage-undetermined" not in analysis.approval_reasons

    synthetic = [
        requirement for requirement in analysis.requirements if requirement.concept is None
    ]
    assert len(synthetic) == 1
    assert synthetic[0].coverage == "undetermined"
    assert synthetic[0].mandatory is False
    assert [component.component_id for component in synthetic[0].missing_components] == [
        "unmapped-statement"
    ]
    # Scored, not withheld - and scored below what the mapped statement alone
    # would have produced.
    assert analysis.fit_score is not None
    assert analysis.fit_score < 1.0


def test_both_new_reasons_are_answered_only_by_accepting_an_incomplete_analysis() -> None:
    """Same override as `extraction-failed`, and no classification override.

    Naming a Track or Profile does not make the engine have read the posting,
    and `accepted-low-fit` answers a different claim entirely ("the candidate
    fits poorly", not "we could not tell").
    """
    for reason in ("requirements-absent", "requirements-unmapped"):
        entry = APPROVAL_REASONS[reason]
        assert entry.overrides == frozenset({"analysis"}), reason
        assert entry.review_code == ANALYSIS_INCOMPLETE, reason
        assert not entry.overrides & {"track", "profile", "emphasis", "language", "fit"}, reason
