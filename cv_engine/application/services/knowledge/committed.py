"""Knowledge as last committed, refused while a cross-store mutation is in flight.

A Knowledge mutation replaces a file and then commits its database half
(architecture §7.2). While its journal entry is `PREPARED` the files may already
hold the new content and the database not yet, so a read in that window would
see Knowledge the lifecycle trail does not describe. Reads made outside a
transaction refuse it here, in their own read scope.

Inside a transaction the caller checks the journal through its own token and reads
the files directly: the Operation handlers do exactly that, since a second scope
cannot open inside theirs. Reconciliation reads the files directly too: reporting
a `PREPARED` entry is its job, not something to refuse.
"""

from __future__ import annotations

from ....domain.facts import FactStore
from ....domain.knowledge import Knowledge
from ...errors import KnowledgeRejected
from ...ports.knowledge_lifecycle import KnowledgeLifecycleStore
from ...ports.outbound import KnowledgeStore
from ...ports.transactions import TransactionManager


def refuse_prepared_knowledge(
    transactions: TransactionManager, journal: KnowledgeLifecycleStore
) -> None:
    with transactions.read() as tx:
        prepared = journal.prepared_mutations(tx)
    if prepared:
        raise KnowledgeRejected("Knowledge has an uncommitted prepared mutation")


class CommittedKnowledge:
    """The Knowledge files, read only while no mutation is `PREPARED`."""

    def __init__(
        self,
        files: KnowledgeStore,
        *,
        transactions: TransactionManager,
        journal: KnowledgeLifecycleStore,
    ):
        self._files = files
        self._transactions = transactions
        self._journal = journal

    def load(self) -> Knowledge:
        refuse_prepared_knowledge(self._transactions, self._journal)
        return self._files.load()

    def facts(self) -> FactStore:
        refuse_prepared_knowledge(self._transactions, self._journal)
        return self._files.facts()
