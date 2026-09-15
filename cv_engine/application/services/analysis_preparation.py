"""Prepare provider-backed analyses before durable activation."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.analysis.approval import ACCEPTED_INCOMPLETE_ANALYSIS
from ...domain.analysis.assembly import build_analysis
from ...domain.analysis.requirements.ai_extraction import (
    RequirementExtractionRejected,
    extraction_is_failed,
    verify_and_cover_extraction,
)
from ...domain.analysis.requirements.segmentation import requirement_lines
from ...domain.contracts.analysis import JobAnalysis, OverrideKey
from ...domain.contracts.selection import SelectionManifest
from ..commands import AnalyzeCommand
from ..errors import (
    ApplicationError,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    ProviderInvalidOutput,
    UnknownRecord,
)
from ..ports import JobAnalysisContext, RequirementExtractionContext
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
    extraction_evidence: ProviderEvidence | None = None


class AnalysisPreparation:
    @staticmethod
    def prepare(
        service, command: AnalyzeCommand, *, operation_id: str | None = None
    ) -> PreparedAnalysis:
        """Validate and compute an analysis without mutating durable application state.

        `operation_id` is required. It is
        where the sanitized provider response is preserved, and it is the
        Operation's own ID rather than the analysis's, so a retry - which is
        a second Operation - writes beside the first attempt's evidence
        instead of colliding with it.
        """
        try:
            snapshot = service.repo.get_snapshot(command.job_snapshot_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job snapshot: {command.job_snapshot_id}") from exc
        if snapshot["application_id"] != command.application_id:
            raise LineageBroken(
                f"job snapshot {command.job_snapshot_id} does not belong to application "
                f"{command.application_id}"
            )
        try:
            job_text = service.snapshot_payloads.read_snapshot(
                snapshot["payload_path"],
                snapshot["source_hash"],
            )
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not read job snapshot payload: {exc}") from exc
        knowledge = service.load_knowledge()
        profiles = knowledge.profiles
        if command.provider != "openai" or operation_id is None:
            raise PreconditionFailed("analysis requires an OpenAI Operation")
        evidence: ProviderEvidence | None = None
        extraction_evidence: ProviderEvidence | None = None
        try:
            extracted_answer = service.provider.propose_requirement_extraction(
                RequirementExtractionContext(
                    job_text=job_text,
                    requirement_lines=[
                        {
                            "start": line.start,
                            "end": line.end,
                            "text": line.text,
                            "section": line.section,
                        }
                        for line in requirement_lines(job_text, knowledge.requirement_concepts)
                    ],
                    candidate_facts=analysis_fact_context(knowledge.facts),
                ),
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
            extraction_evidence = service.preserve(
                command.application_id,
                operation_id,
                "propose_requirement_extraction",
                extracted_answer.provenance,
            )
            try:
                (
                    verified_requirements,
                    unmapped,
                    understanding,
                    unmatched_lines,
                ) = verify_and_cover_extraction(
                    extracted_answer.proposal,
                    source_text=job_text,
                    normalized_hash=snapshot["normalized_hash"],
                    facts=knowledge.facts,
                    concepts=knowledge.requirement_concepts,
                    task_version=extracted_answer.provenance.context.task_contract_version,
                    prompt_version=extracted_answer.provenance.context.prompt_version,
                )
            except RequirementExtractionRejected as exc:
                # The sanitized response was already preserved and registered
                # above via `service.preserve` (invariant 15: a refused output
                # stays inactive immutable evidence rather than being dropped
                # at the raise site). `.evidence` is set, not just
                # `provenance=`, so `_preserve_rejected` finds it already
                # registered and only adds the missing Operation output
                # reference - calling `service.preserve` a second time on the
                # same payload would collide on `artifact_versions.path`
                # UNIQUE, exactly as that function's docstring warns against.
                failure = ProviderInvalidOutput(str(exc), provenance=extracted_answer.provenance)
                failure.evidence = extraction_evidence
                raise failure from exc
            extraction_namespace = (
                f"ai:{extracted_answer.provenance.context.task_contract_version}:"
                f"{extracted_answer.provenance.context.prompt_version}"
            )
            override_candidates: dict[OverrideKey, str | None] = {
                "track": command.track_override,
                "profile": command.profile_override,
                "emphasis": command.emphasis_override,
                "language": command.language_override,
            }
            overrides: dict[OverrideKey, str] = {
                key: value for key, value in override_candidates.items() if value is not None
            }
            answered = service.provider.propose_job_analysis(
                JobAnalysisContext(
                    job_text=job_text,
                    requirements=[item.model_dump(mode="json") for item in verified_requirements],
                    overrides={str(key): value for key, value in overrides.items()},
                ),
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
            evidence = service.preserve(
                command.application_id, operation_id, "propose_job_analysis", answered.provenance
            )
            try:
                result = build_analysis(
                    requirements=verified_requirements,
                    extraction_version=extraction_namespace,
                    extraction_failed=extraction_is_failed(
                        job_text, verified_requirements, knowledge.requirement_concepts
                    ),
                    requirements_absent=not verified_requirements,
                    requirements_unmapped=bool(unmatched_lines) and bool(verified_requirements),
                    proposal=answered.proposal,
                    profiles=profiles,
                    facts=knowledge.facts,
                    unmapped_statements=unmapped,
                    understanding=understanding,
                    overrides=overrides,
                )
            except ValueError as exc:
                failure = ProviderInvalidOutput(str(exc), provenance=answered.provenance)
                failure.evidence = evidence
                raise failure from exc
            used_provider = answered.provenance.context.provider
            used_model = answered.provenance.context.model
        except ApplicationError as exc:
            exc.completed_evidence = tuple(
                item for item in (extraction_evidence, evidence) if item is not None
            )
            raise

        accepted: dict[str, str] = {
            **({"fit": "accepted-low-fit"} if command.accept_low_fit else {}),
            **(
                {"analysis": ACCEPTED_INCOMPLETE_ANALYSIS}
                if command.accept_incomplete_analysis
                else {}
            ),
        }
        if accepted:
            # Rebuilt through validation rather than model_copy(update=...), which
            # would skip the model validators that guard this state.
            accepted_overrides = {**result.user_override, **accepted}
            result = JobAnalysis.model_validate(
                {**result.model_dump(mode="json"), "user_override": accepted_overrides}
            )

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
            extraction_evidence=extraction_evidence,
        )
