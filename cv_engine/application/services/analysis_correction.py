"""Apply explicit user classification corrections to an existing analysis."""

from __future__ import annotations

from ...domain.analysis.approval import (
    ACCEPTED_INCOMPLETE_ANALYSIS,
)
from ...domain.analysis.assembly import rebase_requirements
from ...domain.analysis.requirements.ai_extraction import apply_interpretation_corrections
from ...domain.contracts.analysis import JobAnalysis, OverrideKey
from ...domain.contracts.selection import SelectionPlan
from ...domain.contracts.taxonomy import Emphasis
from ...domain.profiles import classification_mismatch
from ...util import utc_now
from ..commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
    CreateSelectionPlanCommand,
)
from ..errors import (
    InfrastructureFailure,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from .analysis_preparation import PreparedAnalysis
from .analysis_selection import AnalysisSelection


def revise_classification(
    analysis: JobAnalysis, merged_overrides: dict[str, str], profiles
) -> JobAnalysis:
    profile = type(analysis.profile)(merged_overrides.get("profile", analysis.profile.value))
    track = type(analysis.track)(merged_overrides.get("track", analysis.track.value))
    selected = profiles.get(profile)
    emphasis = type(analysis.emphasis)(merged_overrides.get("emphasis", analysis.emphasis.value))
    mismatch = classification_mismatch(selected, track, emphasis)
    if mismatch == "track":
        raise PreconditionFailed(
            f"Track {track.value} and Profile {profile.value} are inconsistent"
        )
    if mismatch == "emphasis":
        raise PreconditionFailed(
            f"Emphasis {emphasis.value} is not allowed for Profile {profile.value}"
        )
    return analysis.model_copy(
        update={
            "track": track,
            "profile": profile,
            "emphasis": emphasis,
            "language": merged_overrides.get("language", analysis.language),
            "user_override": merged_overrides,
        }
    )


class AnalysisCorrection:
    @staticmethod
    def apply_analysis_decisions(
        service, command: ApplyAnalysisDecisionsCommand
    ) -> AnalysisDecisionsResult:
        """§13: one review-form submission, and the branch it actually takes.

        Meaning changed -> one new immutable JobAnalysis carrying the overrides,
        together with its initial deterministic SelectionPlan, committed
        atomically by `save_analysis`. Only Emphasis, fact selection, or gap
        acceptance changed -> one replacement SelectionPlan against the same
        analysis. Neither branch touches the records the user decided against.

        Accepting a hard gap is a *selection* decision, not a meaning one. It
        does not change what the requirement means, what it covers, or how it
        is classified - only that the user proceeds despite it - so it creates
        a replacement SelectionPlan and leaves the JobAnalysis alone. That also
        keeps one acceptance from re-deriving an analysis the user never asked
        to change.

        Accepting a low Fit is still an analysis-level override, and it now
        clears `LOW_FIT_REQUIRES_ACCEPTANCE` alone. It used to clear every hard
        gap with it, so one checkbox dismissed deficiencies the user had never
        been shown.

        Decisions accumulate. The submission is merged over the overrides the
        source analysis already carried, so a second decision does not silently
        drop the first, and withholding a field is not a retraction of it.
        """
        service.load_active_application(command.application_id)
        if command.expected_analysis_id != command.job_analysis_id:
            raise StateConflict(
                "the analysis addressed by the request does not match the analysis "
                "observed by the form"
            )
        record = service._analysis_record(command.application_id, command.job_analysis_id)
        analysis: JobAnalysis = record["analysis"]

        candidates: dict[OverrideKey, str | None] = {
            "track": command.track_override,
            "profile": command.profile_override,
            "language": command.language_override,
        }
        submitted: dict[OverrideKey, str] = {
            key: value for key, value in candidates.items() if value
        }
        if command.accept_low_fit:
            submitted["fit"] = "accepted-low-fit"
        if command.accept_incomplete_analysis:
            submitted["analysis"] = ACCEPTED_INCOMPLETE_ANALYSIS
        merged = {**analysis.user_override, **submitted}
        active_plan: SelectionPlan | None = None
        if command.expected_selection_plan_id is not None:
            try:
                observed_plan = service.repo.selection_plan(command.expected_selection_plan_id)
            except UnknownRecord:
                observed_plan = None
            if (
                observed_plan is not None
                and observed_plan.application_id == command.application_id
                and observed_plan.job_analysis_id == command.job_analysis_id
            ):
                active_plan = observed_plan
        prior_emphasis_override = (
            active_plan.plan.emphasis_override if active_plan is not None else None
        )
        requested_emphasis_override = (
            Emphasis(command.emphasis_override) if command.emphasis_override is not None else None
        )
        emphasis_decision_changed = requested_emphasis_override is not None and (
            prior_emphasis_override != requested_emphasis_override
        )
        has_interpretation_corrections = bool(command.requirement_interpretations)
        previous_meaning = {
            key: value for key, value in analysis.user_override.items() if key != "emphasis"
        }
        submitted_meaning = {key: value for key, value in merged.items() if key != "emphasis"}
        changes_meaning = submitted_meaning != previous_meaning or has_interpretation_corrections
        has_fact_overlay = bool(command.pinned_fact_ids or command.excluded_fact_ids)
        has_overlay = bool(
            has_fact_overlay or command.accepted_requirement_ids or emphasis_decision_changed
        )

        # A plan-level Emphasis decision is folded into a newly-created
        # analysis only when another decision already requires that new
        # analysis. Otherwise the JobAnalysis stays immutable and only the
        # SelectionPlan changes.
        carried_emphasis = requested_emphasis_override or prior_emphasis_override
        if changes_meaning and carried_emphasis is not None:
            merged["emphasis"] = carried_emphasis.value

        if has_interpretation_corrections:
            # Stage-1 plan §3.5: a correction re-covers the named requirements
            # under their new interpretation and rebuilds gaps/Fit from the
            # result - it does not re-run classification or re-extract from
            # the provider, so it goes through its own path rather than
            # a new provider analysis, which would do both.
            if has_fact_overlay:
                raise PreconditionFailed(
                    "a classification decision creates a new analysis with its own initial "
                    "SelectionPlan; apply the fact overlay to that analysis in a second command"
                )
            result = service._correct_interpretations(command, analysis, record, merged)
            return AnalysisDecisionsResult(
                application_id=command.application_id,
                job_analysis_id=result.analysis_id,
                selection_plan_id=result.selection_plan_id,
                created_analysis=True,
                analysis=result.analysis,
                plan=service.repo.selection_plan(result.selection_plan_id),
            )

        if changes_meaning and has_fact_overlay:
            # A classification decision produces a *new* analysis whose initial
            # plan is the deterministic one for that classification. Applying a
            # *fact* overlay to it would silently attach decisions the user made
            # about the old candidate accounting to a new one they have not seen.
            #
            # A gap acceptance is not that. It names a requirement rather than a
            # fact, requirement identity is keyed on the snapshot text rather
            # than on the classification, and it is re-checked against the new
            # analysis before it is stored - so it rides along, in the same
            # write, instead of being refused and re-submitted against a record
            # the user never asked to create.
            raise PreconditionFailed(
                "a classification decision creates a new analysis with its own initial "
                "SelectionPlan; apply the fact overlay to that analysis in a second command"
            )

        if changes_meaning:
            result = service._revise_classification(command, analysis, record, merged)
            return AnalysisDecisionsResult(
                application_id=command.application_id,
                job_analysis_id=result.analysis_id,
                selection_plan_id=result.selection_plan_id,
                created_analysis=True,
                analysis=result.analysis,
                plan=service.repo.selection_plan(result.selection_plan_id),
            )

        if not has_overlay:
            # Refused rather than answered with the plan that already exists: an
            # empty submission that created a second identical plan would put a
            # decision in the history that nobody made.
            raise PreconditionFailed("the submitted decisions change nothing")

        created = service.create_selection_plan(
            CreateSelectionPlanCommand(
                application_id=command.application_id,
                job_analysis_id=command.job_analysis_id,
                pinned_fact_ids=list(command.pinned_fact_ids),
                excluded_fact_ids=list(command.excluded_fact_ids),
                emphasis_override=(
                    requested_emphasis_override.value
                    if requested_emphasis_override is not None
                    else None
                ),
                accepted_requirement_ids=list(command.accepted_requirement_ids),
                acceptance_reason=command.acceptance_reason,
                expected_selection_plan_id=command.expected_selection_plan_id,
                enforce_expected_selection_plan=True,
                refuse_matching_context_operation=True,
            )
        )
        return AnalysisDecisionsResult(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            selection_plan_id=created.selection_plan_id,
            created_analysis=False,
            analysis=analysis,
            plan=created.plan,
        )

    @staticmethod
    def revise_classification(
        service,
        command: ApplyAnalysisDecisionsCommand,
        analysis: JobAnalysis,
        record: dict,
        merged_overrides: dict[str, str],
    ) -> AnalysisResult:
        """Create a user-revised analysis without invoking an extractor or provider."""
        knowledge = service.load_knowledge()
        revised = revise_classification(analysis, merged_overrides, knowledge.profiles)
        selected = AnalysisSelection.profile(revised, knowledge.profiles)
        manifest = AnalysisSelection.manifest(revised, knowledge)
        return service.activate(
            AnalyzeCommand(
                application_id=command.application_id,
                job_snapshot_id=record["job_snapshot_id"],
                accepted_requirement_ids=list(command.accepted_requirement_ids),
                acceptance_reason=command.acceptance_reason,
                expected_analysis_id=command.expected_analysis_id,
                expected_selection_plan_id=command.expected_selection_plan_id,
                refuse_matching_context_operation=True,
            ),
            PreparedAnalysis(
                result=revised,
                plan_manifest=manifest,
                provider="user",
                model="classification-correction-v1",
                candidate_context_version=knowledge.candidate.context_version,
                candidate_context_hash=knowledge.candidate.version_hash,
                profile_version=knowledge.profiles.version,
                selection_policy_version=knowledge.policies.version,
                track_emphasis_dependencies={
                    "track": revised.track.value,
                    "emphasis": revised.emphasis.value,
                },
                normalized_role=selected.normalized_role,
            ),
        )

    @staticmethod
    def correct_interpretations(
        service,
        command: ApplyAnalysisDecisionsCommand,
        analysis: JobAnalysis,
        record: dict,
        merged_overrides: dict[str, str],
    ) -> AnalysisResult:
        """Stage-1 plan §3.5: re-cover the named requirements, not re-classify.

        Track, Profile, and Emphasis are untouched - a correction is a claim
        about what one requirement means, not a new classification. Every
        corrected interpretation passes the same interpretation gate a
        provider's original claim did, against the same signed snapshot text,
        so a correction cannot introduce a reading the gate would have refused
        from a provider.
        """
        snapshot = service.repo.get_snapshot(record["job_snapshot_id"])
        try:
            job_text = service.snapshot_payloads.read_snapshot(
                snapshot["payload_path"],
                snapshot["source_hash"],
            )
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not read job snapshot payload: {exc}") from exc
        knowledge = service.load_knowledge()

        corrected_requirements, decisions = apply_interpretation_corrections(
            list(analysis.requirements),
            list(command.requirement_interpretations),
            source_text=job_text,
            normalized_hash=snapshot["normalized_hash"],
            facts=knowledge.facts,
            concepts=knowledge.requirement_concepts,
            actor="user",
            decided_at=utc_now(),
            prior_analysis_id=command.job_analysis_id,
        )
        rebased = rebase_requirements(
            analysis,
            requirements=corrected_requirements,
            extraction_version=analysis.extraction_version,
            facts=knowledge.facts,
            # A correction changes one requirement's interpretation, not
            # whether the extraction as a whole read the posting - that
            # signal is carried forward from the analysis being corrected
            # rather than re-derived, since only a fresh extraction run can
            # actually change it.
            extraction_failed="extraction-failed" in analysis.approval_reasons,
            # Same reasoning, same inheritance: whether the posting stated any
            # requirement, and whether one of its statements went unmapped, are
            # properties of the text. A correction does not re-read the text, so
            # neither can be re-derived here - only carried forward.
            requirements_absent="requirements-absent" in analysis.approval_reasons,
            requirements_unmapped="requirements-unmapped" in analysis.approval_reasons,
        )
        result = rebased.model_copy(
            update={
                "analysis_version": "2.0",
                "user_override": merged_overrides,
                "interpretation_decisions": [
                    *(analysis.interpretation_decisions or []),
                    *decisions,
                ],
            }
        )

        selected_profile = AnalysisSelection.profile(result, knowledge.profiles)
        plan_manifest = AnalysisSelection.manifest(result, knowledge)

        prepared = PreparedAnalysis(
            result=result,
            plan_manifest=plan_manifest,
            # This record was produced by a user's interpretation correction,
            # not by a fresh provider analysis.
            provider="correction",
            model="interpretation-correction-v1",
            candidate_context_version=knowledge.candidate.context_version,
            candidate_context_hash=knowledge.candidate.version_hash,
            profile_version=knowledge.profiles.version,
            selection_policy_version=knowledge.policies.version,
            track_emphasis_dependencies={
                "track": result.track.value,
                "emphasis": result.emphasis.value,
            },
            normalized_role=selected_profile.normalized_role,
        )
        return service.activate(
            AnalyzeCommand(
                application_id=command.application_id,
                job_snapshot_id=record["job_snapshot_id"],
                accepted_requirement_ids=list(command.accepted_requirement_ids),
                acceptance_reason=command.acceptance_reason,
                expected_analysis_id=command.expected_analysis_id,
                expected_selection_plan_id=command.expected_selection_plan_id,
                refuse_matching_context_operation=True,
            ),
            prepared,
        )
