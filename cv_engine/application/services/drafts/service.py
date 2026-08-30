"""The working-draft application service, assembled from its use-case groups."""

from __future__ import annotations

from .approval import DraftApproval
from .archival import DraftArchival
from .decisions import DecisionExport
from .editing import DraftEditing
from .generation import DraftGeneration
from .regeneration import DraftRegeneration
from .selection import DraftSelectionChange
from .validation import DraftValidation


class DraftService(
    DraftGeneration,
    DraftEditing,
    DraftValidation,
    DraftSelectionChange,
    DraftRegeneration,
    DraftArchival,
    DraftApproval,
    DecisionExport,
):
    """The working draft: generation, manual edits, validation, approval.

    One service, still, because that is what the API and the
    Operation runner hold and what the lifecycle needs: every group here reads
    and writes the same active draft under the same optimistic version. What
    the split changes is where each group is written down - generation no
    longer sits in the same file as approval, and each module states the
    section of the specification it implements.

    The bases are disjoint in the methods they define and share only
    `DraftServiceBase`, so the order below is declaration order, not an
    override chain.
    """
