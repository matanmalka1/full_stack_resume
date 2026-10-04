"""The AI call log: every provider call attempt, appended as soon as it ends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.contracts.providers import AICallRecord
from .transactions import WriteTransaction


@dataclass(frozen=True)
class LoggedAICall:
    """Where one appended attempt landed: its identity and its ordinal for the task."""

    ai_call_id: str
    attempt: int


class AICallLog(Protocol):
    def append(
        self,
        tx: WriteTransaction,
        operation_id: str,
        record: AICallRecord,
        *,
        knowledge_context_hash: str,
    ) -> LoggedAICall:
        """Append one attempt; the store assigns `attempt` under the Operation's row lock.

        Requires only that the Operation exists. An attempt that already happened is
        evidence of a billed call and is recorded whether or not the Operation is
        still running or still held by its runner.
        """
        ...
