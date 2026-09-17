"""Prepare provider-backed analyses before durable activation."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.analysis.normalize import normalize_analysis_proposal
from ...domain.contracts.analysis import JobAnalysis, OverrideKey
from ...domain.contracts.selection import SelectionManifest
from ..commands import AnalyzeCommand
from ..errors import (
    ApplicationError,
    InfrastructureFailure,
    PreconditionFailed,
    ProviderInvalidOutput,
)
from ..ports import AnalysisContext
from .analysis_selection import AnalysisSelection
from .proposals import ProviderEvidence, analysis_fact_context


@dataclass(frozen=True)
class PreparedAnalysis:
    result: JobAnalysis
    plan_manifest: SelectionManifest
    provider: str
    model: str
    candidate_context_version: str
    candidate_context_hash: str
    profile_version: str
    selection_policy_version: str
    track_emphasis_dependencies: dict[str, str]
    normalized_role: str
    evidence: ProviderEvidence | None = None


class AnalysisPreparation:
    @staticmethod
    def prepare(
        service, command: AnalyzeCommand, *, operation_id: str | None = None
    ) -> PreparedAnalysis:
        """Validate and compute an analysis without mutating durable application state.

        `operation_id` is required. It is
        where the sanitized provider response is preserved, and it is the
        Operation's own ID rather than the analysis's. A distinct provider output
        from a retry is written beside the first attempt's evidence. Re-observing
        the same provider-assigned response identity reuses immutable evidence;
        the new Operation still receives its own inactive output reference.
        """
        snapshot = service.snapshot_source(command.application_id, command.job_snapshot_id)
        service.refuse_deleted(snapshot.application_id, snapshot.deleted_at)
        try:
            job_text = service.snapshot_payloads.read_snapshot(
                snapshot.payload_path, snapshot.source_hash
            )
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not read job snapshot payload: {exc}") from exc
        knowledge = service.load_knowledge()
        profiles = knowledge.profiles
        if command.provider != "openai" or operation_id is None:
            raise PreconditionFailed("analysis requires an OpenAI Operation")
        evidence: ProviderEvidence | None = None
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
        try:
            answered = service.provider.propose_analysis(
                AnalysisContext(
                    job_text=job_text,
                    candidate_facts=analysis_fact_context(knowledge.facts),
                    overrides={str(key): value for key, value in overrides.items()},
                ),
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
            evidence = service.preserve(
                command.application_id, operation_id, "propose_analysis", answered.provenance
            )
            try:
                # Normalization does not raise over one bad requirement; what
                # can still fail here is a reading the engine cannot act on at
                # all - a Track/Profile/Emphasis combination the Profile does
                # not allow, or a language outside the supported set.
                result = normalize_analysis_proposal(
                    answered.proposal,
                    source_text=job_text,
                    facts=knowledge.facts,
                    profiles=profiles,
                    concepts=knowledge.requirement_concepts,
                    normalized_hash=snapshot.normalized_hash,
                    overrides=overrides,
                )
            except ValueError as exc:
                failure = ProviderInvalidOutput(str(exc), provenance=answered.provenance)
                failure.evidence = evidence
                raise failure from exc
            used_provider = answered.provenance.context.provider
            used_model = answered.provenance.context.model
        except ApplicationError as exc:
            exc.completed_evidence = tuple(item for item in (evidence,) if item is not None)
            raise

        # Checked before anything is written. An analysis whose Track, Profile,
        # and Emphasis disagree can never produce a draft, so persisting it would
        # only leave the application classified by a combination the engine
        # refuses to act on.
        selected_profile = AnalysisSelection.profile(result, profiles)
        plan_manifest = AnalysisSelection.manifest(result, knowledge)

        return PreparedAnalysis(
            result=result,
            plan_manifest=plan_manifest,
            provider=used_provider,
            model=used_model,
            candidate_context_version=knowledge.candidate.context_version,
            candidate_context_hash=knowledge.candidate.version_hash,
            profile_version=profiles.version,
            selection_policy_version=knowledge.policies.version,
            track_emphasis_dependencies={
                "track": result.track.value,
                "emphasis": result.emphasis.value,
            },
            normalized_role=selected_profile.normalized_role,
            evidence=evidence,
        )
