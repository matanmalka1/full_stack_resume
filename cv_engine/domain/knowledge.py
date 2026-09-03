from __future__ import annotations

from dataclasses import dataclass

from ..util import canonical_json, sha256_text
from .analysis.requirements.concepts import RequirementConceptStore
from .contracts.knowledge import CandidateContext
from .facts import FactStore
from .presentations import PresentationStore
from .profiles import ProfileStore
from .selection import EmphasisPolicyStore

#: Dependencies only the analysis stage reads. The requirement vocabulary
#: decides what a posting demands; every stage after analysis consumes the
#: analysis it produced - an immutable record - and never the vocabulary that
#: produced it.
ANALYSIS_ONLY_DEPENDENCIES = frozenset({"requirement_concepts"})


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
    requirement_concepts: RequirementConceptStore

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
            "requirement_concepts": self.requirement_concepts.version,
        }

    def document_versions(self) -> dict[str, str]:
        """The dependencies every stage after analysis actually consumes.

        One hash used to cover all of them, so editing the requirement concepts
        declared the inputs of a draft, its validation and a render changed -
        none of which read that file. A submitted draft then failed activation,
        and a recorded validation stopped describing its own draft, because the
        vocabulary that had produced an immutable analysis moved afterwards.
        """
        return {
            name: version
            for name, version in self.versions().items()
            if name not in ANALYSIS_ONLY_DEPENDENCIES
        }

    def context_hash(self) -> str:
        """What an analysis is measured against: everything it may have read."""
        return sha256_text(canonical_json(self.versions()))

    def document_context_hash(self) -> str:
        """What every stage after analysis is measured against."""
        return sha256_text(canonical_json(self.document_versions()))
