"""The Profile an analysis's classification selects, or the refusal that says why."""

from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.knowledge import Profile
from ....domain.profiles import ProfileStore, classification_mismatch
from ...errors import PreconditionFailed, StateConflict


def analysis_profile(analysis: JobAnalysis, profiles: ProfileStore) -> Profile:
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
