"""Selection policy shared by analysis activation and later document selection changes."""

from __future__ import annotations

from dataclasses import dataclass

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.knowledge import Profile
from ....domain.contracts.providers import SelectionProposal
from ....domain.contracts.selection import SelectionManifest
from ....domain.profiles import ProfileStore, classification_mismatch
from ....domain.selection import MissingFactRendering as DomainMissingFactRendering
from ....domain.selection import build_selection, pin_capacity
from ...commands import ProposeSelectionCommand
from ...errors import MissingFactRendering, PreconditionFailed, StateConflict
from ..proposals import ProviderEvidence


@dataclass(frozen=True)
class PreparedSelectionProposal:
    """A provider's selection overlay, already validated by selection policy."""

    command: ProposeSelectionCommand
    proposal: SelectionProposal
    evidence: ProviderEvidence
    selection: SelectionManifest


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

    @staticmethod
    def _line_groups(analysis: JobAnalysis, profile: Profile, knowledge):
        if knowledge.presentations is None:
            return None
        return knowledge.presentations.line_groups(profile, analysis.emphasis)

    @classmethod
    def pin_capacity(cls, analysis: JobAnalysis, knowledge) -> dict[str, int]:
        profile = cls.profile(analysis, knowledge.profiles)
        return pin_capacity(
            analysis=analysis,
            profile=profile,
            policy=knowledge.policies.get(analysis.emphasis),
            facts=knowledge.facts,
            line_groups=cls._line_groups(analysis, profile, knowledge),
        )

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
                line_groups=cls._line_groups(analysis, profile, knowledge),
                **overlays,
            )
            return manifest
        except DomainMissingFactRendering as exc:
            raise MissingFactRendering(exc.fact_id, exc.language) from exc
        except ValueError as exc:
            raise PreconditionFailed(f"selection plan could not be built: {exc}") from exc
