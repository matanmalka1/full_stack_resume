from __future__ import annotations

from dataclasses import dataclass

from .facts import FactStore
from .models import CandidateContext
from .presentations import PresentationStore
from .profiles import ProfileStore
from .selection import EmphasisPolicyStore


@dataclass(frozen=True)
class Knowledge:
    """The version-controlled knowledge one command runs against.

    Loaded as a set rather than piecemeal so a single command cannot mix facts
    read at one moment with profiles read at another, and so every dependency
    it consumed can be reported as one version surface.
    """

    facts: FactStore
    profiles: ProfileStore
    policies: EmphasisPolicyStore
    candidate: CandidateContext
    presentations: PresentationStore | None

    def versions(self) -> dict[str, str]:
        """One hash per dependency an artifact can be stale against.

        Kept per dependency rather than as one store-wide version so an
        unrelated fact change does not have to look like a change to every
        profile, policy, and candidate context.
        """
        return {
            "facts": self.facts.version,
            "facts_lifecycle": self.facts.lifecycle_version,
            "profiles": self.profiles.version,
            "emphasis_policies": self.policies.version,
            "presentations": self.presentations.version if self.presentations is not None else "",
            "candidate_context": self.candidate.version_hash,
        }
