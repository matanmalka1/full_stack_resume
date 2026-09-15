"""Review routing for AI-produced analyses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from ..contracts.analysis import JobAnalysis

ACCEPTED_INCOMPLETE_ANALYSIS = "accepted-incomplete-analysis"
ANALYSIS_INCOMPLETE = "ANALYSIS_INCOMPLETE"


@dataclass(frozen=True)
class ApprovalReason:
    overrides: frozenset[str]
    review_code: str


APPROVAL_REASONS: dict[str, ApprovalReason] = {
    "extraction-failed": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),
    "coverage-undetermined": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),
    "requirements-absent": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),
    "requirements-unmapped": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),
}

UNREGISTERED_REASON = ApprovalReason(frozenset(), ANALYSIS_INCOMPLETE)


def approval_reason(reason: str) -> ApprovalReason:
    return APPROVAL_REASONS.get(reason, UNREGISTERED_REASON)


def resolving_actions(reason: str) -> tuple[str, ...]:
    return ("apply_analysis_decisions",) if approval_reason(reason).overrides else ()


_OverrideKey = TypeVar("_OverrideKey", bound=str)


def unresolved_reasons(reasons: Sequence[str], overrides: Mapping[_OverrideKey, str]) -> list[str]:
    return [
        reason for reason in reasons if not (approval_reason(reason).overrides & overrides.keys())
    ]


def unresolved_approval_reasons(
    analysis: JobAnalysis, additional_overrides: Mapping[str, str] | None = None
) -> list[str]:
    return unresolved_reasons(
        analysis.approval_reasons,
        {**analysis.user_override, **dict(additional_overrides or {})},
    )
