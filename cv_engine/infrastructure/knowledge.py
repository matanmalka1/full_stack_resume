from __future__ import annotations

from pathlib import Path

from ..domain.candidate import load_candidate_context
from ..domain.facts import FactStore
from ..domain.knowledge import Knowledge
from ..domain.presentations import PresentationStore
from ..domain.profiles import ProfileStore
from ..domain.selection import EmphasisPolicyStore


class FileKnowledge:
    """Knowledge as it is actually stored: version-controlled files.

    This is the only place that knows the knowledge layout inside a Workspace.
    Every command re-reads through it rather than holding a long-lived cache,
    so a manual or CLI edit between commands is seen rather than assumed away.
    """

    def __init__(self, knowledge_root: Path):
        self.knowledge_root = Path(knowledge_root)

    @property
    def base_dir(self) -> Path:
        return self.knowledge_root / "base"

    def load(self) -> Knowledge:
        facts = FactStore.load(self.base_dir)
        return Knowledge(
            facts=facts,
            profiles=ProfileStore.load(self.knowledge_root, facts),
            policies=EmphasisPolicyStore.load(self.knowledge_root),
            candidate=load_candidate_context(self.knowledge_root, facts),
            presentations=PresentationStore.for_facts(facts),
        )
