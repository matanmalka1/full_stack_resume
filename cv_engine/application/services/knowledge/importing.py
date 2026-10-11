"""`import-knowledge`: one user's Knowledge from the files into PostgreSQL (architecture §18.7).

The files are read through the same validated loader the application uses, so what is
imported is exactly what the application would run against; Knowledge that does not
load is refused before anything is written. The rows are then read back inside the same
transaction and rebuilt, and the import commits only if they reproduce every fact, every
Profile, and the candidate context it read. A lossy import cannot be committed.

In the same transaction the existing fact events get their owner, the one permitted
change to that history (migration 0005).

The application keeps reading the files until the step that switches it over
(docs/decisions/multi-user-accounts.md §5, step 4); nothing here changes what it reads.
"""

from __future__ import annotations

from ....domain.accounts import EmailRejected, normalize_email
from ....domain.knowledge import Knowledge
from ....domain.knowledge_import import (
    KnowledgeSplitError,
    candidate_payload,
    fact_from_row,
    fact_rows,
    join_profile,
    split_profile,
)
from ....util import utc_now
from ...commands import BoundaryDTO
from ...errors import KnowledgeRejected, PreconditionFailed, StateConflict, UnknownRecord
from ...ports.accounts import AccountRepository
from ...ports.knowledge_lifecycle import KnowledgeLifecycleStore
from ...ports.outbound import KnowledgeStore
from ...ports.transactions import ReadTransaction, TransactionManager
from ...ports.user_knowledge import UserKnowledgeRepository


class KnowledgeImportResult(BoundaryDTO):
    email: str
    facts: int
    profiles: int
    fact_events: int


class KnowledgeImportService:
    def __init__(
        self,
        transactions: TransactionManager,
        accounts: AccountRepository,
        journal: KnowledgeLifecycleStore,
        repository: UserKnowledgeRepository,
    ):
        self.transactions = transactions
        self.accounts = accounts
        self.journal = journal
        self.repo = repository

    def import_knowledge(self, email: str, source: KnowledgeStore) -> KnowledgeImportResult:
        try:
            normalized = normalize_email(email)
        except EmailRejected as error:
            raise PreconditionFailed(str(error)) from None
        with self.transactions.read() as tx:
            user = self.accounts.user_by_email(tx, normalized)
            self._refuse_unresolved_mutation(tx)
        if user is None:
            raise UnknownRecord("No user has this email.")
        try:
            knowledge = source.load()
            bindings = {
                profile.profile_id: split_profile(profile)
                for profile in knowledge.profiles.profiles.values()
            }
        except (KnowledgeSplitError, ValueError) as error:
            raise KnowledgeRejected(f"Knowledge does not load: {error}") from None
        rows = fact_rows(knowledge.facts)
        candidate = candidate_payload(knowledge.candidate)

        with self.transactions.write() as tx:
            # Again where the rows are written: a mutation may have begun since the read.
            self._refuse_unresolved_mutation(tx)
            if self.repo.has_knowledge(tx, user.id):
                raise StateConflict("This user already has Knowledge; import runs once.")
            self.repo.insert_knowledge(
                tx,
                user.id,
                facts=rows,
                candidate=candidate,
                bindings={profile_id: binding for profile_id, (_, binding) in bindings.items()},
                imported_at=utc_now(),
            )
            self._verify_round_trip(
                tx,
                user.id,
                knowledge,
                templates={profile_id: template for profile_id, (template, _) in bindings.items()},
            )
            # Nothing serializes a file mutation against the import, so the files are read
            # again before committing: rows describing files that have since changed are
            # refused, not committed.
            try:
                unchanged = source.load().versions() == knowledge.versions()
            except ValueError:
                unchanged = False
            if not unchanged:
                raise KnowledgeRejected(
                    "Knowledge changed while it was being imported; run the import again."
                )
            # The lifecycle history written before Knowledge had an owner is this user's:
            # the database admits one user (`users_single_user`), so nothing is guessed.
            events = self.repo.assign_unowned_fact_events(tx, user.id)
        return KnowledgeImportResult(
            email=user.email, facts=len(rows), profiles=len(bindings), fact_events=events
        )

    def _refuse_unresolved_mutation(self, tx: ReadTransaction) -> None:
        if self.journal.prepared_mutations(tx) or self.journal.quarantined_mutations(tx):
            # The files may hold content the lifecycle trail does not describe.
            raise KnowledgeRejected(
                "Knowledge has an unresolved mutation; resolve it before importing."
            )

    def _verify_round_trip(
        self,
        tx: ReadTransaction,
        user_id: str,
        knowledge: Knowledge,
        *,
        templates: dict[str, dict],
    ) -> None:
        stored_facts, stored_candidate, stored_bindings = self.repo.stored_knowledge(tx, user_id)
        rebuilt = [fact_from_row(row) for row in stored_facts]
        expected = [
            knowledge.facts.facts[row["fact_id"]]
            for row in sorted(
                fact_rows(knowledge.facts), key=lambda row: (row["source"], row["ordinal"])
            )
        ]
        problems: list[str] = []
        if [fact.fact_id for fact in rebuilt] != [fact.fact_id for fact in expected]:
            problems.append("fact identities or their order")
        else:
            problems.extend(
                f"fact {got.fact_id}"
                for got, want in zip(rebuilt, expected, strict=True)
                if got != want
            )
        if stored_candidate != candidate_payload(knowledge.candidate):
            problems.append("candidate context")
        for profile in knowledge.profiles.profiles.values():
            binding = stored_bindings.get(profile.profile_id)
            if binding is None or join_profile(templates[profile.profile_id], binding) != profile:
                problems.append(f"profile {profile.profile_id}")
        if set(stored_bindings) != set(templates):
            problems.append("the set of profiles")
        if problems:
            # Raised inside the write scope, so nothing of the import is committed.
            raise KnowledgeRejected(
                f"The imported rows do not reproduce the files: {', '.join(problems)}."
            )
