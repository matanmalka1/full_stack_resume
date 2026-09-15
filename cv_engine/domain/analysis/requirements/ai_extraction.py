"""Turn a gate-verified AI requirement proposal into a covered `Requirement`.

Every `ProposedRequirement` reaching this module has already passed the
source gate (`attestation.py`) and the interpretation gate
(`interpretation.py`): its quote is proven to occur in the signed snapshot,
and its `interpretation` has passed policy. What is decided here is coverage
- whether canonical Knowledge verifies it - and under D5 the provider is the
semantic authority for that reading: it proposes a coverage verdict and names
the canonical facts behind it.

The provider does not get the last word. `evidence.py` holds the gates D5
keeps deterministic - every cited fact must exist and be canonical, a
positive reading must retain inspectable evidence, a threshold is recomputed
from the evidence facts' own structured fields rather than taken on report,
and a canonical boundary fact caps `matched` to `partial` on applicability
the vocabulary decides rather than the provider. A composite requirement's
composition arithmetic is likewise the engine's.

What no longer happens here is concept recognition deciding coverage. A
proposed requirement used to map to `config/requirements.json` by pattern,
and a real requirement those six concepts did not model returned
`undetermined` however well the provider read it - the closed-vocabulary
collapse product-spec §2 "Semantic analysis authority" removes. The vocabulary survives where it
states something the posting cannot: which boundary facts apply, and how a
named scale is ordered. Both only ever lower coverage.
"""

from __future__ import annotations

from typing import cast

from ...contracts.analysis import (
    Coverage,
    InterpretationDecision,
    InterpretationOverride,
    MissingComponent,
    Requirement,
    RequirementAttestation,
    RequirementInterpretation,
    RequirementMember,
    UnderstandingSources,
    UnmappedStatement,
)
from ...contracts.providers import (
    ProposedEvidence,
    ProposedMemberCoverage,
    RequirementExtractionProposal,
)
from ...facts import FactStore
from .attestation import InvalidRequirementAttestation, reconcile_attestation
from .concepts import RequirementConceptStore
from .confidence import span_completeness
from .evidence import (
    InvalidRequirementEvidence,
    ProposedCoverage,
    boundary_facts_for_quote,
    decide_coverage,
)
from .identity import (
    normalize_span,
    requirement_id,
    undetermined_requirement,
    unmatched_requirement_lines,
)
from .interpretation import InvalidRequirementInterpretation, verify_interpretation
from .segmentation import StatementLine, overlaps, requirement_lines


def _member_coverage(
    member: RequirementMember,
    proposed: dict[str, ProposedMemberCoverage],
    facts: FactStore,
    concepts: RequirementConceptStore,
    *,
    where: str,
) -> tuple[Coverage, list[str]]:
    """One `any-of`/`all-of` member's coverage, from the evidence proposed for it.

    A member the proposal says nothing about is `undetermined`, never guessed
    at as matched or unsupported: silence about a member is not a finding
    about it. The same gate the top-level requirement passes runs here - cited
    facts must be canonical, a positive reading must have evidence behind it,
    and a boundary fact matching the member's own attested quote caps it -
    because without that a boundary fact would protect every requirement
    except the members of a composite one.

    A member with no attestation is `undetermined` whatever the proposal says
    about it. A bare `label` is a provider's description with no verification
    behind it, so there is no quote for a boundary to apply to and nothing the
    engine could show for a positive reading.
    """
    entry = proposed.get(member.member_id)
    if entry is None or member.attestation is None:
        return "undetermined", []
    decision = decide_coverage(
        proposed=entry.coverage,
        evidence=entry.evidence,
        quote=member.attestation.quote,
        label=member.label,
        kind="presence",
        demanded=None,
        facts=facts,
        concepts=concepts,
        where=f"{where} member {member.member_id!r}",
    )
    return decision.coverage, decision.supporting_fact_ids


def attested_spans(requirements: list[Requirement]) -> list[tuple[int, int]]:
    """Where in the posting this requirement set was actually read.

    Attested spans only. A requirement with no attestation is one the engine
    synthesized for a statement nothing read (`undetermined_requirement`), so
    counting it would let an extraction certify its completeness with the very
    entries that record its failure to be complete.
    """
    return [
        (requirement.attestation.start, requirement.attestation.end)
        for requirement in requirements
        if requirement.attestation is not None
    ]


def cover_ai_requirement(
    quote: str,
    interpretation: RequirementInterpretation,
    *,
    kind: str,
    demanded: str | None,
    coverage_claim: ProposedCoverage,
    evidence: list[ProposedEvidence],
    members_coverage: list[ProposedMemberCoverage],
    label: str,
    requirement_id_value: str,
    facts: FactStore,
    concepts: RequirementConceptStore,
) -> Requirement:
    """Decide coverage for one gate-verified AI requirement (D5).

    `interpretation.negation` is checked first and unconditionally: a negated
    requirement is never positive coverage.

    Everything after that is the provider's reading under `evidence.py`'s
    gates. What this function no longer does is ask
    `concept_for_quote` whether the six concepts in
    `config/requirements.json` happen to model this posting: that gate
    returned `undetermined` for every real requirement outside a closed
    sales vocabulary, whatever the provider read, and the spec's semantic-
    analysis authority supersedes it. The
    vocabulary still decides boundary applicability and scale ordering, both
    of which only ever lower coverage.
    """
    text = normalize_span(quote)
    mandatory = interpretation.obligation == "mandatory"
    where = f"requirement {text[:60]!r}"

    if interpretation.negation:
        return Requirement(
            requirement_id=requirement_id_value,
            text=quote,
            kind="presence",
            mandatory=mandatory,
            coverage="unsupported",
            missing_components=[
                MissingComponent(component_id="negated", label="Negated statement")
            ],
            interpretation=interpretation,
        )

    if interpretation.composition in ("any-of", "all-of"):
        indexed = {entry.member_id: entry for entry in members_coverage}
        results = [
            (member, *_member_coverage(member, indexed, facts, concepts, where=where))
            for member in interpretation.members
        ]
        supporting = sorted({fact_id for _, _, ids in results for fact_id in ids})
        missing = [
            MissingComponent(component_id=member.member_id, label=member.label)
            for member, member_coverage, _ in results
            if member_coverage != "matched"
        ]
        member_coverages = [member_coverage for _, member_coverage, _ in results]
        # The composition arithmetic is the engine's, not the provider's:
        # "internally checkable compositional consistency" is deterministic
        # policy under D5, so the top-level `coverage` claim is not read here
        # at all. A member left undetermined keeps the whole requirement
        # undetermined unless another member already settles it - `any-of` is
        # settled by one match, `all-of` by nothing short of all of them.
        if interpretation.composition == "any-of":
            coverage: Coverage = (
                "matched"
                if "matched" in member_coverages
                else ("undetermined" if "undetermined" in member_coverages else "unsupported")
            )
        else:  # all-of
            coverage = (
                "matched"
                if member_coverages and all(item == "matched" for item in member_coverages)
                else ("undetermined" if "undetermined" in member_coverages else "unsupported")
            )
        boundary = boundary_facts_for_quote(quote, concepts, facts)
        if boundary and coverage == "matched":
            coverage = "partial"
        return Requirement(
            requirement_id=requirement_id_value,
            text=text,
            kind="compositional",
            mandatory=mandatory,
            coverage=coverage,
            supporting_fact_ids=supporting,
            boundary_fact_ids=boundary,
            missing_components=missing if coverage != "matched" else [],
            interpretation=interpretation,
        )

    decision = decide_coverage(
        proposed=coverage_claim,
        evidence=evidence,
        quote=quote,
        label=label or text,
        kind=kind,
        demanded=demanded,
        facts=facts,
        concepts=concepts,
        where=where,
    )
    return Requirement(
        requirement_id=requirement_id_value,
        text=text,
        kind=kind if kind in ("threshold", "compositional", "presence") else "presence",  # type: ignore[arg-type]
        mandatory=mandatory,
        coverage=decision.coverage,
        supporting_fact_ids=decision.supporting_fact_ids,
        boundary_fact_ids=decision.boundary_fact_ids,
        missing_components=decision.missing_components,
        interpretation=interpretation,
    )


def correct_interpretation(
    requirement: Requirement,
    corrected: RequirementInterpretation,
    *,
    demanded: str | None,
    source_text: str,
    normalized_hash: str,
    facts: FactStore,
    concepts: RequirementConceptStore,
) -> Requirement:
    """Re-verify and re-cover one requirement under a corrected interpretation.

    Stage-1 plan §3.5: a correction is a new, documented interpretation, not
    the removal of a gap in place. The corrected interpretation passes the
    same interpretation gate a provider's original claim did - a correction
    is not exempt from the policy it is correcting the record to satisfy -
    and the requirement's own attestation is untouched: what was quoted did
    not change, only how it is read.

    `demanded` must be resupplied by the caller for a threshold requirement:
    it is not stored on `Requirement` itself, only computed at extraction
    time, so a correction has no other way to recover it.

    The requirement id moves, because identity is built from the
    interpretation, `kind`, and `demanded` (`extraction.py::requirement_id`,
    stage-1 plan §3.4). This is what makes a prior gap acceptance not
    silently apply to the corrected requirement's meaning -
    `analysis.py::_acceptable_requirement_ids` already refuses an id that does
    not name a hard gap of the analysis being written, and a moved id is
    exactly such a refusal.
    """
    quote = requirement.attestation.quote if requirement.attestation else requirement.text
    span = (
        (requirement.attestation.start, requirement.attestation.end)
        if requirement.attestation
        else None
    )
    verify_interpretation(
        corrected, source_text=source_text, concepts=concepts, requirement_span=span
    )
    identity_span = normalize_span(quote)
    extractor = requirement.extractor or "corrected"
    new_id = requirement_id(
        normalized_hash=normalized_hash,
        extraction_version=extractor,
        identity_span=identity_span,
        ordinal=0,
        interpretation=corrected,
        kind=requirement.kind,
        demanded=demanded,
    )
    # A correction changes what the posting was read to *mean*, never what
    # the candidate has, so the requirement's existing evidence is carried
    # forward as the claim to re-gate rather than discarded. It is re-gated
    # rather than copied: the corrected interpretation can turn a single
    # requirement into a composite one, whose members nothing has read
    # evidence for yet, and `undetermined` is the honest answer there.
    covered = cover_ai_requirement(
        quote,
        corrected,
        kind=requirement.kind,
        demanded=demanded,
        coverage_claim=cast("ProposedCoverage", requirement.coverage),
        evidence=[
            ProposedEvidence(fact_id=fact_id, rationale="carried from the corrected requirement")
            for fact_id in requirement.supporting_fact_ids
        ],
        members_coverage=[],
        label=requirement.text,
        requirement_id_value=new_id,
        facts=facts,
        concepts=concepts,
    )
    return covered.model_copy(
        update={"attestation": requirement.attestation, "extractor": extractor}
    )


class RequirementExtractionRejected(ValueError):
    """The provider's proposal failed the source or interpretation gate.

    One failure voids the whole proposal (stage-1 plan §3.1/§3.2): there is no
    partial acceptance of a requirement list part of which could not be
    trusted. The application layer catches this and re-raises
    `ProviderInvalidOutput`.
    """


class UnknownRequirementForCorrection(ValueError):
    """An interpretation correction named a requirement the analysis does not have."""


def apply_interpretation_corrections(
    requirements: list[Requirement],
    corrections: list[InterpretationOverride],
    *,
    source_text: str,
    normalized_hash: str,
    facts: FactStore,
    concepts: RequirementConceptStore,
    actor: str,
    decided_at: str,
    prior_analysis_id: str,
) -> tuple[list[Requirement], list[InterpretationDecision]]:
    """Apply every submitted interpretation correction, and record each one.

    Stage-1 plan §3.5: this produces the corrected requirement list and the
    decisions to attach to the new `JobAnalysis` version -
    `rebase_requirements` still does the actual work of rebuilding gaps, Fit,
    and approval routing from the result, exactly as it does for a fresh AI
    extraction. A correction is not a second, parallel way to update those
    fields.

    Refuses rather than ignores a `prior_requirement_id` that does not name a
    requirement of this analysis: a correction that silently did nothing would
    look, from the caller's `changes_meaning` check, exactly like one that
    worked.
    """
    by_id = {requirement.requirement_id: requirement for requirement in requirements}
    corrected_by_id: dict[str, Requirement] = {}
    decisions: list[InterpretationDecision] = []
    for override in corrections:
        requirement = by_id.get(override.prior_requirement_id)
        if requirement is None:
            raise UnknownRequirementForCorrection(
                f"no requirement {override.prior_requirement_id!r} on this analysis to correct"
            )
        corrected = correct_interpretation(
            requirement,
            override.interpretation,
            demanded=override.demanded,
            source_text=source_text,
            normalized_hash=normalized_hash,
            facts=facts,
            concepts=concepts,
        )
        corrected_by_id[requirement.requirement_id] = corrected
        decisions.append(
            InterpretationDecision(
                prior_requirement_id=override.prior_requirement_id,
                prior_analysis_id=prior_analysis_id,
                interpretation=override.interpretation,
                actor=actor,
                decided_at=decided_at,
                reason=override.reason,
            )
        )
    updated = [
        corrected_by_id.get(requirement.requirement_id, requirement) for requirement in requirements
    ]
    return updated, decisions


def verify_and_cover_extraction(
    proposal: RequirementExtractionProposal,
    *,
    source_text: str,
    normalized_hash: str,
    facts: FactStore,
    concepts: RequirementConceptStore,
    task_version: str,
    prompt_version: str,
) -> tuple[list[Requirement], list[UnmappedStatement], UnderstandingSources, list[StatementLine]]:
    """Gate, identify, and cover every requirement an AI extraction proposed.

    The one entry point the application service calls (stage-1 plan §3.7 step
    4-6): every `ProposedRequirement` passes the source gate, then the
    interpretation gate, before any of it is trusted for coverage. A single
    failing requirement rejects the whole proposal - this is a Proposal, not a
    partially-applied edit, and invariant 12/13 draw the line at "nothing here
    can save state" rather than "most of it is fine".

    Requirements are deduplicated by `requirement_id`, so the returned list
    carries each id once. A provider that proposes one requirement twice is
    stating it twice, not demanding it twice; see the loop for why the id is
    the key and why a duplicate is collapsed rather than rejected.

    `UnderstandingSources.by_ai` counts requirement-bearing statements this
    extraction actually covered, using the `requirement_lines` denominator.
    It counts *coverage*, i.e. a
    statement whose offsets a verified requirement or a declared
    unmapped-statement entry touches - not whether that requirement was
    successfully mapped to a concept. A statement handled but left
    `undetermined` was still read; §3.3's `partial` floor for an unmapped,
    unexplained statement is a separate, lower bar this does not soften.

    The extractor namespace is `ai:{task_version}:{prompt_version}` (stage-1
    plan §3.4 table): both the task's own version and the prompt version are
    part of what is being identified, because a prompt change can change what
    the same posting text is read to mean without the task contract itself
    changing.

    The fourth return value is the requirement-bearing statements no verified
    requirement's offsets touched. Each already has an `undetermined`
    `Requirement` spliced into the returned list - a provider that reads one of
    twenty requirements and says nothing about the other nineteen must not
    produce a `fit_score` computed over that one. They are returned as well as
    spliced because the caller needs to know one existed, and re-deriving that
    from the spliced list would mean inferring which entries this function
    synthesized.
    """
    extractor = f"ai:{task_version}:{prompt_version}"
    requirements: list[Requirement] = []
    seen_ids: set[str] = set()
    mapped_spans: list[tuple[int, int]] = []

    for proposed in proposal.requirements:
        try:
            attestation = reconcile_attestation(proposed.attestation, source_text=source_text)
            span = (attestation.start, attestation.end)
            verify_interpretation(
                proposed.interpretation,
                source_text=source_text,
                concepts=concepts,
                requirement_span=span,
            )
        except (InvalidRequirementAttestation, InvalidRequirementInterpretation) as exc:
            raise RequirementExtractionRejected(str(exc)) from exc

        quote = attestation.quote
        identity_span = normalize_span(quote)
        # `ordinal` is constant deliberately. Every field that separates
        # two proposed requirements - quote, interpretation, kind, demanded
        # value - is already folded into the id, and a position on top would
        # only make two statements of one requirement look like two.
        req_id = requirement_id(
            normalized_hash=normalized_hash,
            extraction_version=extractor,
            identity_span=identity_span,
            ordinal=0,
            interpretation=proposed.interpretation,
            kind=proposed.kind,
            demanded=proposed.demanded,
        )
        # Every verified proposal's span counts as read, the duplicates
        # included. The posting really does state this requirement at both
        # offsets, and dropping the second would make `unmatched_requirement_
        # lines` below synthesize an `undetermined` entry for a statement the
        # extraction did cover.
        mapped_spans.append(span)
        # A provider restating one requirement is one requirement - the answer
        # the identity function already gives. Both copies passed both gates,
        # so a duplicate is collapsed rather than rejected; keeping both would
        # price one demand into `fit_score` twice and leave two entries under
        # one id, which nothing holding an id could tell apart. The key is the
        # id itself rather than a hand-copied tuple of its inputs, because
        # `requirement_id` *is* the definition of when two readings are one
        # requirement, so a dedup derived from it cannot drift out of step
        # with it.
        if req_id in seen_ids:
            continue
        seen_ids.add(req_id)
        try:
            covered = cover_ai_requirement(
                quote,
                proposed.interpretation,
                kind=proposed.kind,
                demanded=proposed.demanded,
                coverage_claim=proposed.coverage,
                evidence=proposed.evidence,
                members_coverage=proposed.members_coverage,
                label=proposed.label,
                requirement_id_value=req_id,
                facts=facts,
                concepts=concepts,
            )
        except InvalidRequirementEvidence as exc:
            raise RequirementExtractionRejected(str(exc)) from exc
        requirements.append(
            covered.model_copy(update={"attestation": attestation, "extractor": extractor})
        )

    unmapped: list[UnmappedStatement] = []
    for statement in proposal.unmapped_statements:
        try:
            attestation = reconcile_attestation(
                RequirementAttestation(
                    quote=statement.text, start=statement.start, end=statement.end
                ),
                source_text=source_text,
            )
        except InvalidRequirementAttestation as exc:
            raise RequirementExtractionRejected(str(exc)) from exc
        unmapped.append(
            statement.model_copy(
                update={
                    "text": attestation.quote,
                    "start": attestation.start,
                    "end": attestation.end,
                }
            )
        )
        # Unmapped statements are disclosed separately, not credited as understood.

    unmatched_lines = unmatched_requirement_lines(source_text, concepts, mapped_spans)
    requirements += [
        undetermined_requirement(
            line,
            normalized_hash=normalized_hash,
            extraction_version=extractor,
            ordinal=ordinal,
        )
        for ordinal, line in enumerate(unmatched_lines)
    ]

    # Still counted against `mapped_spans` alone. A statement this function
    # synthesized an `undetermined` entry for was not read by the extraction;
    # crediting it here would make `by_ai` report the denominator back to
    # itself.
    by_ai = sum(
        1
        for line in requirement_lines(source_text, concepts)
        if any(overlaps((line.start, line.end), span) for span in mapped_spans)
    )
    understanding = UnderstandingSources(by_ai=by_ai)
    return requirements, unmapped, understanding, unmatched_lines


def extraction_is_failed(
    source_text: str,
    requirements: list[Requirement],
    concepts: RequirementConceptStore,
) -> bool:
    """Whether no stated requirement was extracted.

    Exactly "completeness is zero", and asked of the one measure that answers
    that (`confidence.span_completeness`) rather than re-deriving the statement
    denominator and the overlap test a third time. It used to do both by hand,
    with a docstring promising the result agreed with the measure that decides
    confidence; now agreeing is not something either of them can fail at.

    `None` completeness - the posting states no requirements at all - is not a
    failure: there was nothing to read. That case is reported separately as
    `requirements-absent`.

    Partial extraction remains distinct from total failure; this predicate does
    not certify completeness and must not be presented as such. An unmapped
    entry explains an omission but does not establish understanding, so the
    proposal's `unmapped_statements` are deliberately not consulted.
    """
    completeness = span_completeness(source_text, attested_spans(requirements), concepts)
    return completeness == 0.0
