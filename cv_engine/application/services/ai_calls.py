"""Every provider call attempt, logged as it ends, and the decision to try once more.

The provider adapter makes exactly one attempt per call and never touches the
database. This service appends that attempt to the AI call log in its own short
write scope *before* it decides anything else, so a crash, a cancellation or a lost
lease between two attempts never loses one that already happened. Only then does it
apply the retry policy - a policy of the application, not an invariant of storage.

Retrying one call never repeats another: the writer and the reviewer of one
Operation are separate calls, so a reviewer that is retried leaves the writer's
answer, already logged, as it was.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from ...domain.contracts.base import StrictModel
from ...domain.contracts.providers import AICallRecord
from ..errors import (
    ExecutionStopped,
    ProviderFailure,
    ProviderQuotaExhausted,
    ProviderRateLimited,
    ProviderRefused,
    ProviderSchemaViolation,
    ProviderTimeout,
    ProviderUnavailable,
)
from ..ports.ai_calls import AICallLog
from ..ports.outbound import AIAttempt
from ..ports.transactions import TransactionManager

ProposalT = TypeVar("ProposalT", bound=StrictModel)

#: Attempts per call, the first included.
MAX_ATTEMPTS = 2
#: A `Retry-After` longer than this is not waited for; the call fails instead.
MAX_RETRY_AFTER_SECONDS = 20.0
#: HTTP statuses retried once, as the provider recommends. Not free of duplicate
#: risk: a 5xx can follow processing the provider already did.
_RETRIED_HTTP_STATUSES = frozenset({500, 503})


def _backoff() -> float:
    return 1.0 + random.random() * 2.0


def retry_delay(
    record: AICallRecord, attempt: int, backoff: Callable[[], float] = _backoff
) -> float | None:
    """Seconds to wait before one more attempt, or None when there is none.

    Retried only where a second call is safe or the provider asks for one:
    - `not_delivered`: proven never sent (name lookup failed, connection refused);
    - `rate_limited` with a `Retry-After` of at most `MAX_RETRY_AFTER_SECONDS`;
    - HTTP 500, and 503 honouring `Retry-After` up to the same limit.
    Never after `outcome_unknown` - the provider may have processed and billed the
    request - nor after quota exhaustion, a refusal, a schema violation or another
    HTTP error.
    """
    if attempt >= MAX_ATTEMPTS:
        return None
    retry_after = record.retry_after_seconds
    if record.outcome == "not_delivered":
        return backoff()
    if record.outcome == "rate_limited":
        if retry_after is None or retry_after > MAX_RETRY_AFTER_SECONDS:
            return None
        return retry_after
    if record.outcome == "http_error" and record.http_status in _RETRIED_HTTP_STATUSES:
        if retry_after is None:
            return backoff()
        return retry_after if retry_after <= MAX_RETRY_AFTER_SECONDS else None
    return None


def failure_for(record: AICallRecord) -> ProviderFailure:
    """The classified failure an unsuccessful final attempt ends the call with."""
    detail = record.detail or "The AI provider call failed."
    outcome = record.outcome
    if outcome == "refused":
        return ProviderRefused(detail)
    if outcome == "schema_violation":
        return ProviderSchemaViolation(detail)
    if outcome == "rate_limited":
        return ProviderRateLimited(detail)
    if outcome == "quota_exhausted":
        return ProviderQuotaExhausted(detail)
    if outcome == "http_error":
        status = record.http_status or 0
        return ProviderUnavailable(detail) if status >= 500 else ProviderRefused(detail)
    if outcome == "outcome_unknown" and record.error_type in ("TimeoutError", "timeout"):
        return ProviderTimeout(detail)
    return ProviderUnavailable(detail)


@dataclass(frozen=True)
class RecordedCall(Generic[ProposalT]):
    """A successful call: the logged attempt that produced the Proposal."""

    ai_call_id: str
    record: AICallRecord
    proposal: ProposalT


class AICallRunner:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        log: AICallLog,
        sleeper: Callable[[float], None] = time.sleep,
        backoff: Callable[[], float] = _backoff,
    ):
        self.transactions = transactions
        self.log = log
        self.sleeper = sleeper
        self.backoff = backoff

    def run(
        self,
        operation_id: str,
        invoke: Callable[[], AIAttempt[ProposalT]],
        *,
        knowledge_context_hash: str,
        still_owned: Callable[[], bool],
    ) -> RecordedCall[ProposalT]:
        """Call, log, and try once more only when the policy and the Operation allow.

        `still_owned` must hold before any further attempt starts: the Operation is
        still running, still held by this runner, and nobody asked to cancel it. It
        is checked again after the wait, which is when a cancellation usually lands.
        """
        attempt = 0
        while True:
            attempt += 1
            result = invoke()
            with self.transactions.write() as tx:
                logged = self.log.append(
                    tx, operation_id, result.record, knowledge_context_hash=knowledge_context_hash
                )
            if result.record.outcome == "succeeded" and result.proposal is not None:
                return RecordedCall(logged.ai_call_id, result.record, result.proposal)
            delay = retry_delay(result.record, attempt, self.backoff)
            if delay is None:
                raise failure_for(result.record)
            if not still_owned():
                raise ExecutionStopped("The Operation was cancelled before a retry.")
            self.sleeper(delay)
            if not still_owned():
                raise ExecutionStopped("The Operation was cancelled before a retry.")
