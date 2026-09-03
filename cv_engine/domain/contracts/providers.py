"""AI proposal and provider-execution provenance contracts."""

from __future__ import annotations

from typing import Any, Literal

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


class SelectionProposal(StrictModel):
    """`propose_selection_plan`: an overlay on the deterministic selection.

    Deliberately expressed as the same two lists a user's review form submits,
    because activation replays the identical deterministic `build_selection`.
    A provider that could return a finished plan could express a selection the
    engine would never make; a provider that returns an overlay cannot.
    """

    pinned_fact_ids: list[str] = []
    excluded_fact_ids: list[str] = []
    rationale: str


class DraftProposal(StrictModel):
    """`draft_resume`: proposed wording for a draft the engine composed."""

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


class ProviderUsage(StrictModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ProviderPricing(StrictModel):
    currency: Literal["USD"] = "USD"
    version: str
    source: str
    input_per_million_usd: str
    cached_input_per_million_usd: str
    output_per_million_usd: str
    long_context_threshold_tokens: int
    long_context_input_multiplier: str
    long_context_output_multiplier: str


class ProviderCost(StrictModel):
    currency: Literal["USD"] = "USD"
    input_usd: str
    output_usd: str
    total_usd: str


class ProviderContext(StrictModel):
    """Exactly what ran, recorded on every provider execution (architecture §11).

    No field here can hold a credential. The key is environment configuration
    that never enters a record, request headers are never captured, and hidden
    reasoning content is never requested or retained - so what is stored is
    the execution's identity and effort setting, not hidden reasoning.
    """

    provider: str
    model: str
    reasoning_effort: str | None = None
    task_contract_version: str
    prompt_version: str
    prompt_hash: str
    system_version: str
    # Architecture §11 requires the input and output schema versions alongside
    # the contract and prompt versions. The declared version is the label the
    # contract file states; the hash is computed from the actual Pydantic schema
    # at call time, so a schema that changes without its version moving is
    # visible in the record rather than only in a diff. Same pairing the prompt
    # already uses, for the same reason.
    input_schema_version: str
    input_schema_hash: str
    output_schema_version: str
    output_schema_hash: str
    response_id: str | None = None
    usage: ProviderUsage = ProviderUsage()
    pricing: ProviderPricing | None = None
    cost: ProviderCost | None = None
    latency_ms: int = 0


class ProviderTaskResult(StrictModel):
    """One provider execution's provenance, and the sanitized bytes to preserve.

    `sanitized_response` is the payload the application commits as an immutable
    artifact; `raw_output_hash` is its hash, and `output_hash` is the hash of
    the parsed output that entered the Proposal. Two hashes because they answer
    two questions: what the provider sent, and what the engine acted on.
    """

    task: str
    output: dict[str, Any]
    context: ProviderContext
    input_hash: str
    output_hash: str
    raw_output_hash: str
    sanitized_response: str
