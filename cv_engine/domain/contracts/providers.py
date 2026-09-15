"""AI proposal and provider-execution provenance contracts."""

from __future__ import annotations

from typing import Any, Literal

from .analysis import RequirementAttestation, RequirementInterpretation, UnmappedStatement
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


class ProposedEvidence(StrictModel):
    """One canonical fact a provider says answers a requirement, and why.

    `fact_id` is a citation, never a proof: `evidence.py` checks that the fact
    exists and is canonical before any of it is read, and a threshold is
    recomputed from the fact's own structured fields rather than from anything
    said here. `rationale` is the provider's account of why this fact answers
    the requirement - preserved because a positive coverage reading has to stay
    inspectable (D5), and read by no decision.
    """

    fact_id: str
    rationale: str


class ProposedMemberCoverage(StrictModel):
    """How the provider read one member of an `any-of`/`all-of` requirement.

    Separate from `RequirementMember`, which lives in the `interpretation` and
    is folded into requirement identity: what the posting *means* is a
    different claim from what the candidate *has*, and merging them would make
    every evidence change a new requirement.

    `member_id` addresses the member inside this proposal only. A member with
    no entry here is `undetermined`, never assumed unsupported - saying nothing
    about a member is not a finding about it.
    """

    member_id: str
    coverage: Literal["matched", "partial", "unsupported", "undetermined"]
    evidence: list[ProposedEvidence] = []


class ProposedRequirement(StrictModel):
    """`propose_requirement_extraction`: one requirement, as the provider read it.

    Deliberately separate from `JobClassificationProposal` (stage-1 plan
    §2.3): mixing extraction into the classification task in one call would
    collapse the separation product-spec §12 is built on - a provider proposes
    classification and a provider proposes what the posting requires are two
    different judgements with two different gates, and merging the call would
    make that invisible at the contract boundary.

    `attestation` and `interpretation` are unverified provider claims until
    the source and interpretation gates run over them; nothing here is trusted
    before that.

    `label` is the provider's own name for the requirement and is deliberately
    not read: the requirement's text comes from the verified quote, for the
    same reason `interpretation_identity_key` is preferred over a
    `member_id` - a provider-chosen label has no verification behind it. It
    stays in the contract because it is what makes a proposal legible in the
    preserved response, not because anything downstream trusts it.

    There is deliberately no topic/tag field. One existed, documented as a
    boundary-association hint under which "a foreign tag disqualifies the
    proposal", and no line of code ever read it - so the contract advertised a
    gate that did not exist while `_strict_schema` still obliged every
    provider to fill the field on every requirement. Nothing replaces it:
    under D5 a canonical boundary fact's applicability is decided
    deterministically from the concept vocabulary's own patterns against the
    verified quote (`evidence.py::boundary_facts_for_quote`), never from a
    provider relation or tag - which D5 names specifically.

    `coverage`, `evidence`, and `members_coverage` are the provider's reading
    of whether canonical Knowledge answers this requirement (D5). They are
    proposals like everything else here: `evidence.py` verifies every cited
    fact is canonical, refuses a positive reading with nothing behind it,
    recomputes a threshold from the facts' own structured fields, and lets a
    canonical boundary fact cap the result. A `compositional` requirement's
    own composition arithmetic is deterministic from `members_coverage`; the
    top-level `coverage` is not read for one.
    """

    attestation: RequirementAttestation
    interpretation: RequirementInterpretation
    kind: Literal["threshold", "compositional", "presence"]
    label: str
    demanded: str | None = None
    coverage: Literal["matched", "partial", "unsupported", "undetermined"] = "undetermined"
    evidence: list[ProposedEvidence] = []
    members_coverage: list[ProposedMemberCoverage] = []


class RequirementExtractionProposal(StrictModel):
    """`propose_requirement_extraction`: every requirement, and what was left over."""

    requirements: list[ProposedRequirement]
    unmapped_statements: list[UnmappedStatement] = []


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
