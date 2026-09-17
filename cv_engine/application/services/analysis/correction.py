"""Apply explicit user corrections and risk decisions to an existing analysis."""

from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis, OverrideKey
from ....domain.contracts.selection import SelectionPlan
from ....domain.contracts.taxonomy import Emphasis
from ....domain.profiles import classification_mismatch
from ...commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
    CreateSelectionPlanCommand,
)
from ...errors import (
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from .preparation import PreparedAnalysis
from .selection import AnalysisSelection


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
        """Apply one explicit matching-configuration or fact-selection change.

        Classification changed -> one new immutable JobAnalysis carrying the overrides,
        together with its initial policy-derived SelectionPlan, committed
        atomically by `save_analysis`. Only Emphasis, fact selection, or gap
        acceptance changed -> one replacement SelectionPlan against the same
        analysis. Neither branch touches the records the user edited against.

        Overrides accumulate. The submission is merged over the overrides the
        source analysis already carried, so a second decision does not silently
        drop the first, and withholding a field is not a retraction of it.
        """
        if command.expected_analysis_id != command.job_analysis_id:
            raise StateConflict(
                "the analysis addressed by the request does not match the analysis "
                "observed by the form"
            )
        record = service.selection_source(command.application_id, command.job_analysis_id)
        service.refuse_deleted(record.application_id, record.deleted_at)
        analysis: JobAnalysis = record.analysis

        candidates: dict[OverrideKey, str | None] = {
            "track": command.track_override,
            "profile": command.profile_override,
            "language": command.language_override,
        }
        submitted: dict[OverrideKey, str] = {
            key: value for key, value in candidates.items() if value
        }
        merged = {**analysis.user_override, **submitted}
        active_plan: SelectionPlan | None = None
        if command.expected_selection_plan_id is not None:
            try:
                observed_plan = service.selection_plan(command.expected_selection_plan_id)
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
        previous_meaning = {
            key: value for key, value in analysis.user_override.items() if key != "emphasis"
        }
        submitted_meaning = {key: value for key, value in merged.items() if key != "emphasis"}
        changes_meaning = submitted_meaning != previous_meaning
        has_fact_overlay = bool(command.pinned_fact_ids or command.excluded_fact_ids)
        has_overlay = bool(has_fact_overlay or emphasis_decision_changed)

        # A plan-level Emphasis decision is folded into a newly-created
        # analysis only when another decision already requires that new
        # analysis. Otherwise the JobAnalysis stays immutable and only the
        # SelectionPlan changes.
        carried_emphasis = requested_emphasis_override or prior_emphasis_override
        if changes_meaning and carried_emphasis is not None:
            merged["emphasis"] = carried_emphasis.value

        if changes_meaning and has_fact_overlay:
            # A classification decision produces a *new* analysis whose initial
            # plan is the deterministic one for that classification. Applying a
            # *fact* overlay to it would silently attach decisions the user made
            # about the old candidate accounting to a new one they have not seen.
            raise PreconditionFailed(
                "a classification decision creates a new analysis with its own initial "
                "SelectionPlan; apply the fact overlay to that analysis in a second command"
            )

        if (changes_meaning or has_overlay) and command.expected_selection_plan_id is None:
            # Two different failures, answered with two different codes. A
            # decision that writes a SelectionPlan must say which plan the user
            # was looking at; omitting that is a malformed request, refused
            # here as a precondition. Naming a plan that has since been
            # replaced is a genuine race, and `_active_plan` answers that one
            # with a conflict. Letting the guard catch both reported a client
            # that forgot the token as if it had lost a race it never entered.
            raise PreconditionFailed(
                "a decision that replaces the SelectionPlan must name the plan it was "
                "made against (expected_selection_plan_id)"
            )

        if changes_meaning:
            result = AnalysisCorrection.revise_classification(
                service, command, analysis, record, merged
            )
            return AnalysisDecisionsResult(
                application_id=command.application_id,
                job_analysis_id=result.analysis_id,
                selection_plan_id=result.selection_plan_id,
                created_analysis=True,
                analysis=result.analysis,
                plan=service.selection_plan(result.selection_plan_id),
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
        record,
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
                job_snapshot_id=record.job_snapshot_id,
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
