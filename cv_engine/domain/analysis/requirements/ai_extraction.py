"""Turn a gate-verified AI requirement proposal into a covered `Requirement`.

Every `ProposedRequirement` reaching this module has already passed the
source gate (`attestation.py`) and the interpretation gate
(`interpretation.py`): its quote is proven to occur in the signed snapshot,
and its `interpretation` has passed policy. What is decided here is coverage
- whether canonical Knowledge verifies it - and that decision rests on one
narrow, disclosed mechanism (stage-1 plan §3.5a): a proposed requirement maps
to a concept in `config/requirements.json` only when that concept's own
`patterns` match the *verified quote itself*, never on the provider's
`topic_tags`, which are consulted only as a boundary-association hint
elsewhere (`coverage.py`).

A pattern match proves only that a concept's wording was **mentioned**. It is
never evidence of coverage by itself: coverage is decided the same way the
deterministic path decides it - `satisfied_evidence`/`threshold_coverage`
against the concept's own declared satisfaction rule - never from
`candidate_fact_ids` alone, which is a candidate-evidence hint the
deterministic path also never treats as proof.

This is concept recognition, not semantic understanding. A real requirement
the vocabulary does not model returns no concept and therefore
`undetermined` coverage - a true statement about what the engine could
verify, not a wrong guess. Extending the vocabulary to recognise more of what
employers ask for is a deliberate, tracked addition to
`config/requirements.json` (D3's exception list), never a special case
written for one company's wording. `undetermined` on an acceptance case in
`tailoring-acceptance-cases.md` is a disclosed limitation of this mechanism,
not a passing result for that case.
"""

from __future__ import annotations

from ...contracts.analysis import (
    Coverage,
    InterpretationDecision,
    InterpretationOverride,
    MissingComponent,
    Requirement,
    RequirementAttestation,
    RequirementInterpretation,
    UnderstandingSources,
    UnmappedStatement,
)
from ...contracts.knowledge import FactStatus
from ...contracts.providers import RequirementExtractionProposal
from ...facts import FactStore
from .attestation import InvalidRequirementAttestation, verify_attestation
from .concepts import RequirementConcept, RequirementConceptStore
from .coverage import satisfied_evidence, threshold_coverage
from .extraction import ExtractedRequirement, normalize_span, requirement_id
from .interpretation import InvalidRequirementInterpretation, verify_interpretation
from .segmentation import requirement_lines


def concept_for_quote(quote: str, concepts: RequirementConceptStore) -> RequirementConcept | None:
    """The one concept whose patterns match this exact verified quote, if any.

    A pattern match proves only that the concept's wording was mentioned in
    the quote - never obligation, negation, composition, or threshold
    satisfaction, all of which come from the verified `interpretation` and
    nowhere else (stage-1 plan §3.5a). Ambiguity - more than one concept
    matching - is refused rather than guessed at: silently picking the first
    match would misclassify coverage as confidently as picking none.
    """
    matches = [
        concept
        for concept in concepts.concepts.values()
        if any(pattern.search(quote) for pattern in concept.patterns)
    ]
    return matches[0] if len(matches) == 1 else None


def _boundary_facts(concept: RequirementConcept, facts: FactStore) -> list[str]:
    return sorted(
        fact_id
        for fact_id in concept.boundary_fact_ids
        if fact_id in facts.facts and facts.facts[fact_id].status is FactStatus.CANONICAL
    )


def _presence_coverage(
    concept: RequirementConcept, facts: FactStore
) -> tuple[Coverage, list[str], list[MissingComponent]]:
    """A presence concept's coverage from its own declared satisfaction rule.

    Mirrors `coverage.py::cover_requirements`'s presence branch exactly:
    `satisfied_evidence` against `concept.satisfied_by_fact_ids` /
    `concept.satisfied_by_tags`, capped by a canonical boundary fact. This is
    deliberately not `candidate_fact_ids` - that function finds *candidate*
    evidence for display and Profile scoring, and was never proof of
    satisfaction on the deterministic path either.
    """
    evidence = satisfied_evidence(
        concept.satisfied_by_fact_ids, concept.satisfied_by_tags, facts, concept.boundary_fact_ids
    )
    boundary = _boundary_facts(concept, facts)
    coverage: Coverage = "matched" if evidence else "unsupported"
    missing = [] if evidence else [MissingComponent(component_id=concept.concept, label=concept.label)]
    if boundary and coverage == "matched":
        coverage = "partial"
    return coverage, evidence, missing


def _compositional_concept_coverage(
    concept: RequirementConcept, facts: FactStore
) -> tuple[Coverage, list[str], list[MissingComponent]]:
    """A compositional concept's own components, each checked independently.

    Mirrors `coverage.py::cover_requirements`'s compositional branch: a
    component with no evidence is missing, and the concept is `matched` only
    when every component is, `partial` when some are, `unsupported` when none
    are - never inferred from `candidate_fact_ids` overlap.
    """
    met: list[str] = []
    supporting: list[str] = []
    missing: list[MissingComponent] = []
    for component in concept.components:
        evidence = satisfied_evidence(
            component.satisfied_by_fact_ids,
            component.satisfied_by_tags,
            facts,
            concept.boundary_fact_ids,
        )
        if evidence:
            met.append(component.component_id)
            supporting.extend(evidence)
        else:
            missing.append(MissingComponent(component_id=component.component_id, label=component.label))
    coverage: Coverage = "matched" if not missing else ("partial" if met else "unsupported")
    boundary = _boundary_facts(concept, facts)
    if boundary and coverage == "matched":
        coverage = "partial"
    return coverage, sorted(set(supporting)), missing


def _member_coverage(
    member_quote: str | None, facts: FactStore, concepts: RequirementConceptStore
) -> tuple[Coverage, list[str], RequirementConcept | None]:
    """One `any-of`/`all-of` member's own coverage, mapped by its attested quote.

    `member_quote` is `None` when the member carries no attestation - a bare
    `label` is a provider's description, not proof, and is never used to map
    or decide coverage (stage-1 plan §3.5a addendum). An unattested or
    unmapped member is `undetermined`, never guessed at as matched or
    unsupported.

    A concept found for the member is checked with the same rules
    `cover_requirements` uses for its own kind - `satisfied_evidence` for
    presence, per-component checks for compositional, `threshold_coverage`
    for threshold - never a blanket "candidate facts exist" shortcut. A
    boundary fact still caps `matched` to `partial` here, exactly as it does
    on the top-level requirement; without this a boundary fact would protect
    every requirement except the members of a composite one.
    """
    if not member_quote:
        return "undetermined", [], None
    concept = concept_for_quote(member_quote, concepts)
    if concept is None:
        return "undetermined", [], None
    if concept.kind == "presence":
        coverage, supporting, _ = _presence_coverage(concept, facts)
        return coverage, supporting, concept
    if concept.kind == "compositional":
        coverage, supporting, _ = _compositional_concept_coverage(concept, facts)
        return coverage, supporting, concept
    # threshold: a bare member quote carries no demanded value of its own to
    # check a threshold against, so it cannot be resolved further here.
    return "undetermined", [], concept


def cover_ai_requirement(
    quote: str,
    interpretation: RequirementInterpretation,
    *,
    kind: str,
    demanded: str | None,
    requirement_id_value: str,
    facts: FactStore,
    concepts: RequirementConceptStore,
) -> Requirement:
    """Decide coverage for one gate-verified AI requirement.

    `interpretation.negation` is checked first and unconditionally: a negated
    requirement is never positive coverage, matching the deterministic rule in
    `coverage.py` (stage-1 plan §3.2 rule 7).
    """
    text = normalize_span(quote)
    if interpretation.negation:
        return Requirement(
            requirement_id=requirement_id_value,
            text=quote,
            kind="presence",
            concept=None,
            mandatory=interpretation.obligation == "mandatory",
            coverage="unsupported",
            missing_components=[MissingComponent(component_id="negated", label="Negated statement")],
            interpretation=interpretation,
        )

    mandatory = interpretation.obligation == "mandatory"

    if interpretation.composition in ("any-of", "all-of"):
        results = [
            (member, *_member_coverage(member.attestation.quote if member.attestation else None, facts, concepts))
            for member in interpretation.members
        ]
        supporting = sorted({fact_id for _, _, ids, _ in results for fact_id in ids})
        missing = [
            MissingComponent(component_id=member.member_id, label=member.label)
            for member, member_coverage, _, _ in results
            if member_coverage != "matched"
        ]
        member_coverages = [member_coverage for _, member_coverage, _, _ in results]
        if interpretation.composition == "any-of":
            coverage: Coverage = (
                "matched"
                if "matched" in member_coverages
                else ("undetermined" if "undetermined" in member_coverages else "unsupported")
            )
        else:  # all-of
            coverage = (
                "matched"
                if all(item == "matched" for item in member_coverages)
                else ("undetermined" if "undetermined" in member_coverages else "unsupported")
            )
        return Requirement(
            requirement_id=requirement_id_value,
            text=text,
            kind="compositional",
            concept=None,
            mandatory=mandatory,
            coverage=coverage,
            supporting_fact_ids=supporting,
            missing_components=missing if coverage != "matched" else [],
            interpretation=interpretation,
        )

    concept = concept_for_quote(quote, concepts)
    if concept is None:
        return Requirement(
            requirement_id=requirement_id_value,
            text=text,
            kind="presence" if kind not in ("threshold", "compositional", "presence") else kind,  # type: ignore[arg-type]
            concept=None,
            mandatory=mandatory,
            coverage="undetermined",
            missing_components=[
                MissingComponent(component_id="unmapped", label="No recognised concept")
            ],
            interpretation=interpretation,
        )

    if concept.kind == "threshold":
        extracted = ExtractedRequirement(
            requirement_id=requirement_id_value,
            concept=concept.concept,
            kind=concept.kind,
            span=quote,
            identity_span=text,
            ordinal=0,
            mandatory=mandatory,
            demanded=demanded,
            start=0,
            end=0,
        )
        coverage, missing_components = threshold_coverage(concept, extracted, facts, concepts.scales)
        supporting = sorted(
            {
                fact_id
                for fact_id in concept.value_fact_ids
                if fact_id in facts.facts and facts.facts[fact_id].status is FactStatus.CANONICAL
            }
        )
    elif concept.kind == "compositional":
        coverage, supporting, missing_components = _compositional_concept_coverage(concept, facts)
    else:
        coverage, supporting, missing_components = _presence_coverage(concept, facts)

    boundary = _boundary_facts(concept, facts)

    return Requirement(
        requirement_id=requirement_id_value,
        text=text,
        kind=concept.kind,
        concept=concept.concept,
        mandatory=mandatory,
        coverage=coverage,
        supporting_fact_ids=supporting,
        boundary_fact_ids=boundary,
        missing_components=missing_components,
        interpretation=interpretation,
    )


def unmapped_statement_ids(
    text: str, mapped_spans: list[tuple[int, int]], concepts: RequirementConceptStore
) -> list[tuple[int, int, str]]:
    """Requirement-bearing statements no verified requirement's offsets touch.

    Same completeness denominator the deterministic path uses
    (`requirement_lines`), so an AI extraction is judged for completeness
    against the identical measure (stage-1 plan §3.3).
    """
    lines = requirement_lines(text, concepts)
    return [
        (line.start, line.end, line.text)
        for line in lines
        if not any(start < line.end and line.start < end for start, end in mapped_spans)
    ]


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
    covered = cover_ai_requirement(
        quote,
        corrected,
        kind=requirement.kind,
        demanded=demanded,
        requirement_id_value=new_id,
        facts=facts,
        concepts=concepts,
    )
    return covered.model_copy(update={"attestation": requirement.attestation, "extractor": extractor})


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
) -> tuple[list[Requirement], list[UnmappedStatement], UnderstandingSources]:
    """Gate, identify, and cover every requirement an AI extraction proposed.

    The one entry point the application service calls (stage-1 plan §3.7 step
    4-6): every `ProposedRequirement` passes the source gate, then the
    interpretation gate, before any of it is trusted for coverage. A single
    failing requirement rejects the whole proposal - this is a Proposal, not a
    partially-applied edit, and invariant 12/13 draw the line at "nothing here
    can save state" rather than "most of it is fine".

    `UnderstandingSources.by_ai` counts requirement-bearing statements this
    extraction actually covered, using the identical `requirement_lines`
    denominator the deterministic path uses, so completeness is comparable
    across extractors (stage-1 plan §3.3). It counts *coverage*, i.e. a
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
    """
    extractor = f"ai:{task_version}:{prompt_version}"
    requirements: list[Requirement] = []
    mapped_spans: list[tuple[int, int]] = []

    for proposed in proposal.requirements:
        span = (proposed.attestation.start, proposed.attestation.end)
        try:
            verify_attestation(proposed.attestation, source_text=source_text)
            verify_interpretation(
                proposed.interpretation,
                source_text=source_text,
                concepts=concepts,
                requirement_span=span,
            )
        except (InvalidRequirementAttestation, InvalidRequirementInterpretation) as exc:
            raise RequirementExtractionRejected(str(exc)) from exc

        quote = proposed.attestation.quote
        identity_span = normalize_span(quote)
        req_id = requirement_id(
            normalized_hash=normalized_hash,
            extraction_version=extractor,
            identity_span=identity_span,
            ordinal=0,
            interpretation=proposed.interpretation,
            kind=proposed.kind,
            demanded=proposed.demanded,
        )
        covered = cover_ai_requirement(
            quote,
            proposed.interpretation,
            kind=proposed.kind,
            demanded=proposed.demanded,
            requirement_id_value=req_id,
            facts=facts,
            concepts=concepts,
        )
        requirements.append(
            covered.model_copy(update={"attestation": proposed.attestation, "extractor": extractor})
        )
        mapped_spans.append(span)

    unmapped: list[UnmappedStatement] = []
    for statement in proposal.unmapped_statements:
        try:
            verify_attestation(
                RequirementAttestation(
                    quote=statement.text, start=statement.start, end=statement.end
                ),
                source_text=source_text,
            )
        except InvalidRequirementAttestation as exc:
            raise RequirementExtractionRejected(str(exc)) from exc
        unmapped.append(statement)
        # Unmapped statements are disclosed separately, not credited as understood.

    lines = requirement_lines(source_text, concepts)
    by_ai = sum(
        1
        for line in lines
        if any(start < line.end and line.start < end for start, end in mapped_spans)
    )
    understanding = UnderstandingSources(by_concepts=0, by_rules=0, by_ai=by_ai)
    return requirements, unmapped, understanding


def extraction_is_failed(
    source_text: str,
    requirements: list[Requirement],
    unmapped: list[UnmappedStatement],
    concepts: RequirementConceptStore,
) -> bool:
    """Whether no stated requirement was extracted.

    An unmapped entry explains an omission but does not establish understanding.
    Partial extraction remains distinct from total failure; this predicate does
    not certify completeness and must not be presented as such.
    """
    lines = requirement_lines(source_text, concepts)
    if not lines:
        return False
    mapped_spans = [
        (requirement.attestation.start, requirement.attestation.end)
        for requirement in requirements
        if requirement.attestation is not None
    ]
    # Declaring a statement unmapped explains the omission; it does not read it.
    # A completely unread posting must retain UNKNOWN and its explicit decision.
    return not any(
        start < line.end and line.start < end
        for line in lines
        for start, end in mapped_spans
    )
