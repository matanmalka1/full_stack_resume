"""Apply explicit matching-configuration decisions: a new analysis, or a selection change."""

from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis, OverrideKey
from ....domain.contracts.taxonomy import Emphasis
from ....domain.profiles import classification_mismatch
from ....util import utc_now
from ...commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
)
from ...errors import PreconditionFailed, StateConflict
from ..documents import (
    build_document_selection,
    built_with,
    lock_document_source,
    require_hash,
    selection_change_body,
)
from .preparation import PreparedAnalysis
from .selection_policy import AnalysisSelection


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
        """§13: apply one explicit matching-configuration or fact-selection decision.

        A change to requirement meaning or to the Track/Profile/language
        classification creates one new immutable JobAnalysis and leaves the
        document untouched (it raises `DOCUMENT_ON_OLDER_ANALYSIS` until
        `build_from_analysis`); when no document exists, the new analysis creates it.
        An Emphasis or fact-selection decision on the document's own analysis updates
        the document selection in place, exactly as `update_selection` does.

        Overrides accumulate. The submission is merged over the overrides the source
        analysis already carried, so a second decision does not silently drop the
        first, and withholding a field is not a retraction of it.
        """
        if command.expected_analysis_id != command.job_analysis_id:
            raise StateConflict(
                "the analysis addressed by the request does not match the analysis "
                "observed by the form"
            )
        record = service.selection_source(command.application_id, command.job_analysis_id)
        service.refuse_deleted(record.application_id, record.deleted_at)
        analysis: JobAnalysis = record.analysis
        document = service.current_document(command.application_id)
        if document is not None:
            if command.expected_document_hash is None:
                raise PreconditionFailed(
                    "a decision made beside a CV document must name it (expected_document_hash)"
                )
            require_hash(document, command.expected_document_hash)

        candidates: dict[OverrideKey, str | None] = {
            "track": command.track_override,
            "profile": command.profile_override,
            "language": command.language_override,
        }
        submitted: dict[OverrideKey, str] = {
            key: value for key, value in candidates.items() if value
        }
        merged = {**analysis.user_override, **submitted}
        own_selection = (
            document.selection
            if document is not None and document.analysis_id == command.job_analysis_id
            else None
        )
        prior_emphasis_override = (
            own_selection.emphasis_override if own_selection is not None else None
        )
        try:
            requested_emphasis_override = (
                Emphasis(command.emphasis_override)
                if command.emphasis_override is not None
                else None
            )
        except ValueError as exc:
            raise PreconditionFailed(f"unknown Emphasis: {command.emphasis_override}") from exc
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

        # An Emphasis decision accompanying a classification change is carried into
        # the new analysis's deterministic selection.
        carried_emphasis = requested_emphasis_override or prior_emphasis_override
        if changes_meaning and carried_emphasis is not None:
            merged["emphasis"] = carried_emphasis.value

        if changes_meaning and has_fact_overlay:
            # Pinned and excluded facts are decided against candidate accounting the
            # new analysis has not produced yet, so they stay a second command.
            raise PreconditionFailed(
                "a classification decision creates a new analysis with its own "
                "deterministic selection; apply the fact overlay in a second command"
            )

        if changes_meaning:
            result = AnalysisCorrection.revise_classification(
                service, command, analysis, record, merged
            )
            current = service.current_document(command.application_id)
            return AnalysisDecisionsResult(
                application_id=command.application_id,
                job_analysis_id=result.analysis_id,
                created_analysis=True,
                analysis=result.analysis,
                document_id=current.id if current is not None else None,
                document_hash=current.document_hash if current is not None else None,
            )

        if not has_overlay:
            # Refused rather than answered: an empty submission would put a decision
            # in the history that nobody made.
            raise PreconditionFailed("the submitted decisions change nothing")
        if own_selection is None or document is None or command.expected_document_hash is None:
            raise PreconditionFailed(
                "a selection decision applies to the analysis the document is built on; "
                "build the document from this analysis first"
            )
        knowledge = service.load_knowledge()
        source = service.document_source(command.application_id)
        require_hash(source.document, command.expected_document_hash)
        body = selection_change_body(
            source,
            knowledge,
            pinned_fact_ids=command.pinned_fact_ids,
            excluded_fact_ids=command.excluded_fact_ids,
            emphasis_override=command.emphasis_override,
        )
        with service.transactions.write() as tx:
            service.analyses.lock_application(tx, command.application_id)
            service.analyses.refuse_matching_context_operation(tx, command.application_id)
            locked = lock_document_source(
                tx, service.documents, service.sources, command.application_id
            )
            if locked.latest_analysis_id != command.expected_analysis_id:
                raise StateConflict(
                    "the active JobAnalysis moved since this decision was made "
                    "(expected_analysis_id)"
                )
            updated = service.documents.update_body(
                tx,
                command.application_id,
                command.expected_document_hash,
                body,
                updated_at=utc_now(),
            )
            if emphasis_decision_changed:
                service.analyses.set_matching_emphasis(
                    tx, command.application_id, body.selection.emphasis.value
                )
        return AnalysisDecisionsResult(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            created_analysis=False,
            analysis=analysis,
            document_id=updated.id,
            document_hash=updated.document_hash,
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
        return service.activate(
            AnalyzeCommand(
                application_id=command.application_id,
                job_snapshot_id=record.job_snapshot_id,
                expected_analysis_id=command.expected_analysis_id,
                expected_document_hash=command.expected_document_hash,
                refuse_matching_context_operation=True,
            ),
            PreparedAnalysis(
                result=revised,
                selection=build_document_selection(revised, knowledge),
                built_with=built_with(knowledge),
                provider="user",
                model="classification-correction-v1",
                normalized_role=selected.normalized_role,
            ),
        )
