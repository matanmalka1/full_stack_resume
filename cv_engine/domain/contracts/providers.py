"""AI proposal and provider-execution provenance contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .base import StrictModel


class ProposedClaim(StrictModel):
    """One line a provider proposes, with the facts it says support it.

    `fact_ids` is not proof. A valid ID paired with strengthened wording is the
    failure mode invariant 12 names, so every proposed line still passes the
    same semantic support check a manual edit passes; the IDs only say which
    facts the check is run against.
    """

    section: str
    claim_id: str | None = None
    text: str
    fact_ids: list[str] = []


class DraftProposal(StrictModel):
    """`draft_resume`: the frame claims the writer keeps, with their wording.

    The engine composed every fact each section offers. A claim left out is a fact
    the writer did not choose; headings, dates and contacts stay whether or not they
    come back.
    """

    claims: list[ProposedClaim]
    rationale: str


class SectionProposal(StrictModel):
    """`regenerate_section`: proposed wording for one named section."""

    section: str
    claims: list[ProposedClaim]
    rationale: str


class ClaimProposal(StrictModel):
    """`regenerate_claim`: proposed wording for one named claim."""

    claim_id: str
    text: str
    fact_ids: list[str]
    rationale: str


class ReviewedAssertion(StrictModel):
    """One factual assertion in proposed wording and its exact source evidence."""

    claim_quote: str
    fact_ids: list[str]
    source_quotes: list[str]


class ClaimSupportAssessment(StrictModel):
    claim_id: str
    verdict: Literal["supported", "uncertain", "unsupported"]
    assertions: list[ReviewedAssertion]
    rationale: str


class ClaimSupportProposal(StrictModel):
    """Reviewer output; application policy still decides eligibility."""

    assessments: list[ClaimSupportAssessment]


class ProviderUsage(StrictModel):
    """Token counts as the provider reported them for one call.

    `cached_input_tokens` and `cache_write_tokens` are both part of `input_tokens`:
    every input token is billed once, as ordinary, cached, or cache-write input.
    `cache_write_tokens` is None when the provider did not report it; a cost that
    depends on it is then unknown rather than computed as if it were zero.
    """

    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _consistent(self) -> ProviderUsage:
        if self.cached_input_tokens + (self.cache_write_tokens or 0) > self.input_tokens:
            raise ValueError("cached and cache-write tokens exceed input tokens")
        if self.total_tokens < max(self.input_tokens, self.output_tokens):
            raise ValueError("total tokens are less than input or output tokens")
        return self


class ProviderPricing(StrictModel):
    currency: Literal["USD"] = "USD"
    version: str
    source: str
    input_per_million_usd: str
    cached_input_per_million_usd: str
    cache_write_per_million_usd: str
    output_per_million_usd: str
    long_context_threshold_tokens: int
    long_context_input_multiplier: str
    long_context_output_multiplier: str


class ProviderCost(StrictModel):
    currency: Literal["USD"] = "USD"
    input_usd: str
    output_usd: str
    total_usd: str


#: How one provider call ended. `succeeded` is the only outcome with a parsed
#: Proposal. `not_delivered` is a failure proven to have happened before the request
#: reached the provider; `outcome_unknown` is every transport failure that cannot be
#: proven so, and the provider may have processed and billed it.
AICallOutcome = Literal[
    "succeeded",
    "refused",
    "schema_violation",
    "rate_limited",
    "quota_exhausted",
    "http_error",
    "not_delivered",
    "outcome_unknown",
]


class AICallRecord(StrictModel):
    """One provider call attempt, as it is written to the AI call log.

    Built by the provider adapter for every attempt, successful or not, and appended
    by the application before it decides anything else - so an attempt that already
    happened is never lost to a later failure. No field can hold a credential: the
    key never enters a record, headers are never captured, and hidden reasoning is
    removed before `sanitized_response` exists.

    `sanitized_response` is the provider's envelope after sanitization, in canonical
    JSON form; `sanitized_response_hash` is `sha256(canonical_json(...))` of it, not a
    hash of the bytes the provider sent. `output_hash` is the hash of the parsed
    Proposal the engine acted on. A usage, pricing or cost value is present only when
    the provider reported what it needs.
    """

    task: str
    provider: str
    model: str
    reasoning_effort: str | None = None
    task_contract_version: str
    input_schema_version: str
    input_schema_hash: str
    output_schema_version: str
    output_schema_hash: str
    prompt_version: str
    prompt_hash: str
    input_hash: str
    outcome: AICallOutcome
    http_status: int | None = None
    error_type: str | None = None
    error_code: str | None = None
    retry_after_seconds: float | None = Field(default=None, ge=0)
    response_id: str | None = None
    sanitized_response: dict[str, Any] | None = None
    sanitized_response_hash: str | None = None
    output_hash: str | None = None
    usage: ProviderUsage | None = None
    pricing: ProviderPricing | None = None
    cost: ProviderCost | None = None
    latency_ms: int = Field(ge=0)
    started_at: str
    finished_at: str
    #: Safe English diagnostic for the Operation failure; never stored in the log.
    detail: str = ""
