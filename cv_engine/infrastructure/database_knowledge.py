"""Knowledge read from the user's rows, with policy from the installation's files.

Facts, the candidate context and each Profile's binding are the user's, in PostgreSQL
(architecture §18.2). Profile templates, emphasis policy, presentation rules and
requirement concepts are product policy and stay version-controlled files. A Profile is
its template joined with the user's binding, so it validates exactly as the file
Profile it was imported from did, and hashes the same.

Until isolation gives every request its own user (multi-user-accounts.md §5, step 5)
Knowledge is the installation's one user's: the database admits only one.
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

from ..application.errors import KnowledgeRejected
from ..application.ports.transactions import ReadTransaction, TransactionManager
from ..application.ports.user_knowledge import StoredKnowledge, UserKnowledgeRepository
from ..domain.candidate import build_candidate_context
from ..domain.facts import FactStore
from ..domain.knowledge import Knowledge
from ..domain.knowledge_import import fact_store_from_rows, join_profile, template_of
from ..domain.profiles import ProfileStore, ProfileStoreError
from .knowledge import load_emphasis_policies, load_presentations, load_requirement_concepts

CANDIDATE_ORIGIN = "candidate_contexts"


class DatabaseKnowledge:
    def __init__(
        self,
        transactions: TransactionManager,
        repository: UserKnowledgeRepository,
        policy_root: Path,
    ):
        self._transactions = transactions
        self._repo = repository
        self._root = Path(policy_root).resolve()

    def load(self, tx: ReadTransaction | None = None) -> Knowledge:
        with self._scope(tx) as scope:
            state = self.state(scope)
        return self.build(state)

    def facts(self, tx: ReadTransaction | None = None) -> FactStore:
        with self._scope(tx) as scope:
            state = self.state(scope)
        return fact_store_from_rows(state.facts)

    def state(self, tx: ReadTransaction) -> StoredKnowledge:
        user_id = self._repo.sole_user_id(tx)
        if user_id is None:
            raise KnowledgeRejected("There is no user yet; run create-user, then import-knowledge.")
        state = self._repo.knowledge_state(tx, user_id)
        if state is None:
            raise KnowledgeRejected("This user has no Knowledge yet; run import-knowledge.")
        return state

    def build(self, state: StoredKnowledge) -> Knowledge:
        facts = fact_store_from_rows(state.facts)
        return Knowledge(
            facts=facts,
            profiles=ProfileStore.from_documents(self._profiles(state.bindings), facts),
            policies=load_emphasis_policies(self._root),
            candidate=build_candidate_context(state.candidate, facts, origin=CANDIDATE_ORIGIN),
            presentations=load_presentations(self._root, facts),
            requirement_concepts=load_requirement_concepts(self._root),
        )

    def _scope(self, tx: ReadTransaction | None):
        return nullcontext(tx) if tx is not None else self._transactions.read()

    def _profiles(self, bindings: dict[str, dict]) -> dict[str, dict]:
        """Every template joined with the user's binding, keyed by its file under the root.

        The key is relative (`profiles/sales/...yaml`): it is what a Profile reports as
        its source, and a path on this machine is nobody's business.
        """
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
            origin = path.relative_to(self._root).as_posix()
            documents[origin] = join_profile(template, binding).model_dump(mode="json")
            bound.add(profile_id)
        unknown = sorted(set(bindings) - bound)
        if unknown:
            raise ProfileStoreError(f"bindings name no template: {', '.join(unknown)}")
        return documents
