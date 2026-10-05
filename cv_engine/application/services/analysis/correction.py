"""Apply explicit matching-configuration decisions as a new analysis."""

from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis, OverrideKey
from ....domain.profiles import classification_mismatch
from ...commands import (
    AnalysisDecisionsResult,
    AnalysisResult,
    AnalyzeCommand,
    ApplyAnalysisDecisionsCommand,
)
from ...errors import PreconditionFailed, StateConflict
from ..documents import built_with, require_hash
from .classification import analysis_profile
from .preparation import PreparedAnalysis


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
        """§13: apply one explicit matching-configuration decision.

        A Track, Profile, language, or Emphasis decision creates one new immutable
        JobAnalysis and leaves the document untouched (it raises
        `DOCUMENT_ON_OLDER_ANALYSIS` until `build_from_analysis`); when no document
        exists, the new analysis creates it.

        Overrides accumulate. The submission is merged over the overrides the source
        analysis already carried, so a second decision does not silently drop the
        first, and withholding a field is not a retraction of it.
        """
        if command.expected_analysis_id != command.job_analysis_id:
            raise StateConflict(
                "the analysis addressed by the request does not match the analysis "
                "observed by the form"
            )
        record = service.analysis_context_source(command.application_id, command.job_analysis_id)
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
            "emphasis": command.emphasis_override,
            "language": command.language_override,
        }
        submitted: dict[OverrideKey, str] = {
            key: value for key, value in candidates.items() if value
        }
        merged = {**analysis.user_override, **submitted}
        if merged == analysis.user_override:
            # Refused rather than answered: an empty submission would put a decision
            # in the history that nobody made.
            raise PreconditionFailed("the submitted decisions change nothing")

        result = AnalysisCorrection.revise_classification(
            service, command, analysis, record, merged
        )
        current = service.current_document(command.application_id)
        return AnalysisDecisionsResult(
            application_id=command.application_id,
            job_analysis_id=result.analysis_id,
            analysis=result.analysis,
            document_id=current.id if current is not None else None,
            document_hash=current.document_hash if current is not None else None,
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
        selected = analysis_profile(revised, knowledge.profiles)
        return service.activate(
            AnalyzeCommand(
                application_id=command.application_id,
                job_text_hash=record.job_text_hash,
                expected_analysis_id=command.expected_analysis_id,
                expected_document_hash=command.expected_document_hash,
                refuse_matching_context_operation=True,
            ),
            PreparedAnalysis(
                result=revised,
                built_with=built_with(knowledge),
                provider="user",
                model="classification-correction-v1",
                normalized_role=selected.normalized_role,
            ),
        )
