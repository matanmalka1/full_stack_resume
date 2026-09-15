"""Apply explicit user classification corrections to an existing analysis."""

from __future__ import annotations

from ...domain.analysis.approval import unresolved_approval_reasons
from ...domain.contracts.analysis import JobAnalysis
from ..errors import PreconditionFailed


def revise_classification(
    analysis: JobAnalysis, merged_overrides: dict[str, str], profiles
) -> JobAnalysis:
    profile = type(analysis.profile)(merged_overrides.get("profile", analysis.profile.value))
    track = type(analysis.track)(merged_overrides.get("track", analysis.track.value))
    selected = profiles.get(profile)
    if selected.track is not track:
        raise PreconditionFailed(
            f"Track {track.value} and Profile {profile.value} are inconsistent"
        )
    emphasis = type(analysis.emphasis)(merged_overrides.get("emphasis", analysis.emphasis.value))
    if emphasis not in selected.allowed_emphases:
        raise PreconditionFailed(
            f"Emphasis {emphasis.value} is not allowed for Profile {profile.value}"
        )
    revised = analysis.model_copy(
        update={
            "track": track,
            "profile": profile,
            "emphasis": emphasis,
            "language": merged_overrides.get("language", analysis.language),
            "user_override": merged_overrides,
        }
    )
    return revised.model_copy(
        update={"classification_requires_approval": bool(unresolved_approval_reasons(revised))}
    )
