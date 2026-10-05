"""Prepare provider-backed analyses before durable activation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ....domain.analysis.normalize import normalize_analysis_proposal
from ....domain.contracts.analysis import JobAnalysis, OverrideKey
from ....domain.contracts.document import BuiltWith
from ...commands import AnalyzeCommand
from ...errors import PreconditionFailed, ProviderInvalidOutput
from ...ports import AnalysisContext
from ..proposals import analysis_fact_context
from .classification import analysis_profile


@dataclass(frozen=True)
class PreparedAnalysis:
    """One analysis, computed but not written.

    `built_with` is the Knowledge versions it was built with: it becomes the CV
    document's when this analysis is the Application's first (§13), and is otherwise
    unused.
    """

    result: JobAnalysis
    built_with: BuiltWith
    provider: str
    model: str
    normalized_role: str


class AnalysisPreparation:
    @staticmethod
    def prepare(
        service,
        command: AnalyzeCommand,
        *,
        operation_id: str | None = None,
        still_owned: Callable[[], bool] = lambda: True,
    ) -> PreparedAnalysis:
        """Validate and compute an analysis without mutating durable application state.

        `operation_id` is required: every provider attempt is logged against the
        Operation, not the analysis. `still_owned` is what the runner checks before
        any retry; a caller outside the runner has no lease to lose.
        """
        source = service.job_text_source(command.application_id, command.job_text_hash)
        service.refuse_deleted(source.application_id, source.deleted_at)
        job_text = source.job_text
        knowledge = service.load_knowledge()
        profiles = knowledge.profiles
        if command.provider != "openai" or operation_id is None:
            raise PreconditionFailed("analysis requires an OpenAI Operation")
        override_candidates: dict[OverrideKey, str | None] = {
            "track": command.track_override,
            "profile": command.profile_override,
            "emphasis": command.emphasis_override,
            "language": command.language_override,
        }
        overrides: dict[OverrideKey, str] = {
            key: value for key, value in override_candidates.items() if value is not None
        }
        service.assert_provider_io_allowed()
        context = AnalysisContext(
            job_text=job_text,
            candidate_facts=analysis_fact_context(knowledge.facts),
            overrides={str(key): value for key, value in overrides.items()},
        )
        recorded = service.ai_calls.run(
            operation_id,
            lambda: service.provider.propose_analysis(
                context, model=command.model, reasoning_effort=command.reasoning_effort
            ),
            knowledge_context_hash=knowledge.context_hash(),
            still_owned=still_owned,
        )
        try:
            # Normalization does not raise over one bad requirement; what
            # can still fail here is a reading the engine cannot act on at
            # all - a Track/Profile/Emphasis combination the Profile does
            # not allow, or a language outside the supported set.
            result = normalize_analysis_proposal(
                recorded.proposal,
                source_text=job_text,
                facts=knowledge.facts,
                profiles=profiles,
                concepts=knowledge.requirement_concepts,
                normalized_hash=source.normalized_hash,
                overrides=overrides,
            )
        except ValueError as exc:
            raise ProviderInvalidOutput(str(exc)) from exc

        # Checked before anything is written. An analysis whose Track, Profile,
        # and Emphasis disagree can never produce a draft, so persisting it would
        # only leave the application classified by a combination the engine
        # refuses to act on.
        selected_profile = analysis_profile(result, profiles)

        return PreparedAnalysis(
            result=result,
            built_with=BuiltWith(profile_version=profiles.version),
            provider=recorded.record.provider,
            model=recorded.record.model,
            normalized_role=selected_profile.normalized_role,
        )
