"""Selection policy shared by analysis activation and later plan changes."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.knowledge import Profile
from ...domain.contracts.providers import SelectionProposal
from ...domain.contracts.selection import SelectionManifest
from ...domain.profiles import ProfileStore, classification_mismatch
from ...domain.selection import MissingFactRendering as DomainMissingFactRendering
from ...domain.selection import build_selection
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
        mismatch = classification_mismatch(selected, analysis.track, analysis.emphasis)
        if mismatch == "track":
            raise StateConflict(
                f"Track {analysis.track.value} and Profile {analysis.profile.value} are inconsistent"
            )
        if mismatch == "emphasis":
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
