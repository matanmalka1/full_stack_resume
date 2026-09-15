"""Selection policy shared by analysis activation and later plan changes."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.knowledge import Profile
from ...domain.contracts.providers import SelectionProposal
from ...domain.contracts.selection import AcceptedGap, SelectionManifest
from ...domain.profiles import ProfileStore
from ...domain.selection import MissingFactRendering as DomainMissingFactRendering
from ...domain.selection import build_selection
from ...util import utc_now
from ..commands import CreateSelectionPlanCommand
from ..errors import MissingFactRendering, PreconditionFailed, StateConflict
from .proposals import ProviderEvidence


@dataclass(frozen=True)
class PreparedSelectionProposal:
    command: CreateSelectionPlanCommand
    proposal: SelectionProposal
    evidence: ProviderEvidence


class AnalysisSelection:
    @staticmethod
    def profile(analysis: JobAnalysis, profiles: ProfileStore) -> Profile:
        try:
            selected = profiles.get(analysis.profile)
        except (KeyError, ValueError) as exc:
            raise PreconditionFailed(f"analysis selected an unavailable Profile: {exc}") from exc
        if analysis.track is not selected.track:
            raise StateConflict(
                f"Track {analysis.track.value} and Profile {analysis.profile.value} are inconsistent"
            )
        if analysis.emphasis not in selected.allowed_emphases:
            raise StateConflict(
                f"Emphasis {analysis.emphasis.value} is not allowed for Profile {analysis.profile.value}"
            )
        return selected

    @classmethod
    def manifest(cls, analysis: JobAnalysis, knowledge, **overlays) -> SelectionManifest:
        profile = cls.profile(analysis, knowledge.profiles)
        try:
            _, manifest = build_selection(
                analysis=analysis,
                profile=profile,
                policy=knowledge.policies.get(analysis.emphasis),
                policy_store_version=knowledge.policies.version,
                facts=knowledge.facts,
                line_groups=(
                    knowledge.presentations.line_groups(profile, analysis.emphasis)
                    if knowledge.presentations is not None
                    else None
                ),
                **overlays,
            )
            return manifest
        except DomainMissingFactRendering as exc:
            raise MissingFactRendering(exc.fact_id, exc.language) from exc
        except ValueError as exc:
            raise PreconditionFailed(f"selection plan could not be built: {exc}") from exc

    @staticmethod
    def acceptable_requirement_ids(
        requirement_ids: list[str], analysis: JobAnalysis, expected_plan_id: str | None
    ) -> list[str]:
        if not requirement_ids:
            return []
        if expected_plan_id is None:
            raise PreconditionFailed("accepting a gap requires expected_selection_plan_id")
        hard = {
            gap.requirement_id
            for gap in analysis.gaps
            if gap.severity == "hard" and gap.requirement_id is not None
        }
        unknown = sorted(set(requirement_ids) - hard)
        if unknown:
            raise PreconditionFailed(
                f"no hard gap to accept for requirement(s): {', '.join(unknown)}"
            )
        return requirement_ids

    @classmethod
    def new_acceptances(cls, command, analysis: JobAnalysis) -> list[AcceptedGap]:
        accepted = cls.acceptable_requirement_ids(
            list(command.accepted_requirement_ids), analysis, command.expected_selection_plan_id
        )
        now = utc_now()
        return [
            AcceptedGap(
                requirement_id=requirement_id,
                job_analysis_id=command.job_analysis_id,
                actor="user",
                accepted_at=now,
                reason=command.acceptance_reason,
            )
            for requirement_id in sorted(set(accepted))
        ]
