"""`export-knowledge`: one user's Knowledge from PostgreSQL into the file layout.

The inverse of `import-knowledge`, and how a user's Knowledge reaches another
installation: the files written here are what `import-knowledge --from` reads. The
installation's own `profiles/` hold templates only, so they cannot be imported.

The export proves itself as the import does: the written files are loaded back through
the same validated loader, and must reproduce every fact, every Profile and the
candidate context the rows held. Only the fact-store versions may move, because the
rows keep no per-file source version (architecture §18.2).
"""

from __future__ import annotations

from collections.abc import Callable

from ....domain.accounts import EmailRejected, normalize_email
from ....domain.knowledge import Knowledge
from ...commands import BoundaryDTO
from ...errors import KnowledgeRejected, PreconditionFailed, UnknownRecord
from ...ports.accounts import AccountRepository
from ...ports.outbound import KnowledgeStore
from ...ports.transactions import TransactionManager
from ...ports.user_knowledge import UserKnowledgeSource

#: `Knowledge.versions()` entries a file round trip may change: per-file source versions.
FACT_VERSIONS = frozenset({"facts", "facts_lifecycle"})


class KnowledgeExportResult(BoundaryDTO):
    email: str
    facts: int
    profiles: int


class KnowledgeExportService:
    def __init__(
        self,
        transactions: TransactionManager,
        accounts: AccountRepository,
        knowledge: UserKnowledgeSource,
    ):
        self.transactions = transactions
        self.accounts = accounts
        self.knowledge = knowledge

    def export_knowledge(
        self, email: str, write: Callable[[Knowledge], KnowledgeStore]
    ) -> KnowledgeExportResult:
        """Write the user's Knowledge with `write`, then refuse a copy that is not exact."""
        try:
            normalized = normalize_email(email)
        except EmailRejected as error:
            raise PreconditionFailed(str(error)) from None
        with self.transactions.read() as tx:
            user = self.accounts.user_by_email(tx, normalized)
            if user is None:
                raise UnknownRecord("No user has this email.")
            knowledge = self.knowledge.load(user.id, tx)
        try:
            written = write(knowledge).load()
        except ValueError as error:
            raise KnowledgeRejected(f"The exported files do not load: {error}") from None
        problems = _differences(knowledge, written)
        if problems:
            raise KnowledgeRejected(
                f"The exported files do not reproduce the rows: {', '.join(problems)}."
            )
        return KnowledgeExportResult(
            email=user.email,
            facts=len(knowledge.facts.facts),
            profiles=len(knowledge.profiles.profiles),
        )


def _differences(stored: Knowledge, written: Knowledge) -> list[str]:
    problems: list[str] = []
    if list(written.facts.facts.items()) != list(stored.facts.facts.items()):
        problems.append("facts")
    if written.profiles.profiles != stored.profiles.profiles:
        problems.append("profiles")
    if written.candidate != stored.candidate:
        problems.append("candidate context")
    changed = sorted(
        name
        for name, version in stored.versions().items()
        if name not in FACT_VERSIONS and written.versions().get(name) != version
    )
    problems.extend(f"{name} version" for name in changed)
    return problems
