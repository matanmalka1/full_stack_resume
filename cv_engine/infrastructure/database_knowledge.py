"""Knowledge read from one user's rows, with policy from the installation's files.

Facts, the candidate context and each Profile's binding are the user's, in PostgreSQL
(architecture §18.2). Profile templates, emphasis policy, presentation rules and
requirement concepts are product policy and stay version-controlled files. A Profile is
its template joined with the user's binding, so it validates exactly as the file
Profile it was imported from did, and hashes the same.

The application does not read through this yet; the switch is the next step of
docs/decisions/multi-user-accounts.md §5, step 4.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..application.errors import KnowledgeRejected
from ..application.ports.transactions import ReadTransaction
from ..application.ports.user_knowledge import UserKnowledgeRepository
from ..domain.candidate import build_candidate_context
from ..domain.knowledge import Knowledge
from ..domain.knowledge_import import fact_store_from_rows, join_profile, template_of
from ..domain.profiles import ProfileStore, ProfileStoreError
from .knowledge import load_emphasis_policies, load_presentations, load_requirement_concepts

CANDIDATE_ORIGIN = "candidate_contexts"


class DatabaseKnowledge:
    def __init__(self, repository: UserKnowledgeRepository, policy_root: Path):
        self._repo = repository
        self._root = Path(policy_root).resolve()

    def load(self, tx: ReadTransaction, user_id: str) -> Knowledge:
        rows, candidate, bindings = self._repo.stored_knowledge(tx, user_id)
        if candidate is None:
            raise KnowledgeRejected("This user has no Knowledge yet; run import-knowledge.")
        facts = fact_store_from_rows(rows)
        return Knowledge(
            facts=facts,
            profiles=ProfileStore.from_documents(self._profiles(bindings), facts),
            policies=load_emphasis_policies(self._root),
            candidate=build_candidate_context(candidate, facts, origin=CANDIDATE_ORIGIN),
            presentations=load_presentations(self._root, facts),
            requirement_concepts=load_requirement_concepts(self._root),
        )

    def _profiles(self, bindings: dict[str, dict]) -> dict[str, dict]:
        """Every template joined with the user's binding, keyed by the template's file."""
        documents: dict[str, dict] = {}
        bound: set[str] = set()
        for path in sorted((self._root / "profiles").glob("**/*.yaml")):
            try:
                template = template_of(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError as exc:
                raise ProfileStoreError(f"invalid profile {path}: {exc}") from exc
            profile_id = template["profile_id"]
            binding = bindings.get(profile_id)
            if binding is None:
                raise ProfileStoreError(f"profile {profile_id} has no binding for this user")
            documents[str(path)] = join_profile(template, binding).model_dump(mode="json")
            bound.add(profile_id)
        unknown = sorted(set(bindings) - bound)
        if unknown:
            raise ProfileStoreError(f"bindings name no template: {', '.join(unknown)}")
        return documents
