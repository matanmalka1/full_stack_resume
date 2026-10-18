"""Structural scorers for a tailored CV: did a prompt, contract, or model change help?

Pure functions over the engine's own types - no I/O, no provider, no database - so
the same scorer reads a scripted test draft and a live one alike. Each answers one
measurable question with a number, a list, or a small dataclass.

None of them repeats what the engine already enforces. Canonical facts, pool
membership, the safe headline, and structure are refused or blocked by the engine
itself; a scorer for them would only ever read zero. What is scored here is what
the engine deliberately leaves to the writer's judgement - which facts to keep,
whether to word them for the job, how to weigh the Profile's guidance - and so
what a prompt change can move without any test noticing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cv_engine.application.operations import OperationView
from cv_engine.domain.analysis.document_coverage import (
    COVERED,
    requirements_missing_from_document,
)
from cv_engine.domain.contracts.analysis import JobAnalysis, Requirement
from cv_engine.domain.contracts.drafts import ClaimLine, DraftDocument
from cv_engine.domain.contracts.knowledge import Profile
from cv_engine.domain.drafts import EXTRACTIVE_DERIVATION
from cv_engine.domain.facts import FactStore
from cv_engine.domain.frame import ROLE_BLOCK_TAG, STRUCTURAL_STYLES

__all__ = [
    "PageFitOutcome",
    "budget_adherence",
    "evidence_lines",
    "injection_requirements",
    "mandatory_requirement_recall",
    "page_fit_outcome",
    "requirements_quoting",
    "reworded_share",
    "withheld_rate",
]


def evidence_lines(content: DraftDocument) -> list[ClaimLine]:
    """Every section line that is evidence rather than structure, in document order."""
    return [
        claim
        for section in content.sections
        for claim in section.claims
        if claim.style not in STRUCTURAL_STYLES
    ]


def _recallable(requirement: Requirement) -> bool:
    """The predicate `requirements_missing_from_document` scores against."""
    return (
        requirement.importance == "mandatory"
        and requirement.coverage in COVERED
        and bool(requirement.supporting_fact_ids)
    )


def mandatory_requirement_recall(
    analysis: JobAnalysis, content: DraftDocument | None
) -> float | None:
    """The share of covered mandatory requirements the written CV still evidences.

    The denominator is every requirement that is mandatory, `matched` or `partial`,
    and lists a supporting fact: what the analysis says the candidate can show for a
    demand the employer will not waive. The numerator is those the document still
    cites a supporting fact for - one is enough. Which are missing is
    `requirements_missing_from_document`, the same rule behind the
    `REQUIREMENT_NOT_IN_DOCUMENT` warning, so the score and the warning cannot
    disagree.

    None when the analysis has no such requirement: there was nothing to recall.
    A document with no content recalls nothing, so it scores 0.0 rather than the
    empty list the warning answers it with.
    """
    recallable = [requirement for requirement in analysis.requirements if _recallable(requirement)]
    if not recallable:
        return None
    if content is None:
        return 0.0
    missing = requirements_missing_from_document(analysis, content)
    return (len(recallable) - len(missing)) / len(recallable)


def _writable_claim_ids(content: DraftDocument) -> set[str]:
    return {content.headline.claim_id, *(claim.claim_id for claim in evidence_lines(content))}


def withheld_rate(operation: OperationView, content: DraftDocument | None) -> float:
    """Withheld lines over the lines the writer could word, in the draft it left.

    Numerator: the Operation's `withheld_claims` - lines whose proposed wording the
    engine or the semantic review refused, each left in its frame wording. Lines the
    page-fit step dropped have already left that list.

    Denominator: the document's headline plus its evidence lines. Neither the
    Operation nor the document records which lines the writer actually reworded -
    an echoed canonical line looks the same as one it never touched - so the
    denominator is every line the writer was free to word and kept: contacts,
    headings, and dates are structure the prompt tells it to leave alone. A withheld
    line is always one of these, so the rate stays within [0, 1].

    A rising rate means the writer is proposing wording its facts do not support -
    the engine catches it, but every caught line is a line left untailored.
    """
    if content is None or operation.withheld_claims is None:
        return 0.0
    writable = _writable_claim_ids(content)
    if not writable:
        return 0.0
    withheld = {item.claim_id for item in operation.withheld_claims.claims} & writable
    return len(withheld) / len(writable)


@dataclass(frozen=True)
class PageFitOutcome:
    """What fitting the draft to its page limit did; `status` None when nothing reported."""

    status: str | None
    trimmed: int
    pages: int | None
    maximum: int | None


def page_fit_outcome(operation: OperationView) -> PageFitOutcome:
    """The Operation's page-fit status and how many lines it had to drop.

    A writer that keeps more than the page holds is trimmed by the engine, line by
    line from the bottom of the Profile's ranking - the engine's choice, not the
    writer's, and blind to the job. `trimmed` counting up across runs means the
    writer stopped respecting the length budget; `over` means it kept so much that
    the trim ran out.
    """
    report = operation.page_fit
    if report is None:
        return PageFitOutcome(status=None, trimmed=0, pages=None, maximum=None)
    return PageFitOutcome(
        status=report.status,
        trimmed=len(report.trimmed),
        pages=report.pages,
        maximum=report.maximum,
    )


def _is_role(heading: ClaimLine, facts: FactStore) -> bool:
    return any(
        fact_id in facts.facts and ROLE_BLOCK_TAG in facts.facts[fact_id].tags
        for fact_id in heading.fact_ids
    )


def _role_blocks(claims: list[ClaimLine], facts: FactStore) -> list[tuple[str, int]]:
    """Each role heading in a section, with the evidence lines under it."""
    blocks: list[tuple[str, int]] = []
    current: ClaimLine | None = None
    count = 0
    for claim in claims:
        if claim.style == "heading":
            if current is not None and _is_role(current, facts):
                blocks.append((current.text, count))
            current, count = claim, 0
        elif claim.style not in STRUCTURAL_STYLES:
            count += 1
    if current is not None and _is_role(current, facts):
        blocks.append((current.text, count))
    return blocks


def budget_adherence(content: DraftDocument, profile: Profile, facts: FactStore) -> list[str]:
    """Where the draft departs from its Profile's section guidance, one line per departure.

    Checked per section the document carries:

    - `max_claims`: the section's lines, structure included, over the budget. The
      budget counts every line because it always has: before selection moved to the
      writer, the engine filled the budget with structure and pins first and refused
      a section whose lines exceeded it (`section-budget-exceeded`).
    - `min_claims_per_role` / `max_claims_per_role`: the evidence lines under each
      role title (a heading tagged `historical-title`, as page fit reads it).
    - `pinned_fact_ids`: a pinned fact the section no longer links.

    The writer receives all of this as guidance and nothing enforces it
    (product-spec §10), so a departure is a quality signal, never an error. The
    facts are needed to tell a role title from any other heading. An empty list
    means the draft kept to its guidance.
    """
    specs = {
        (spec.name_he if content.language == "he" else spec.name_en): spec
        for spec in profile.sections
    }
    violations: list[str] = []
    for section in content.sections:
        spec = specs.get(section.name)
        if spec is None:
            continue
        if spec.max_claims is not None and len(section.claims) > spec.max_claims:
            violations.append(
                f"{spec.name_en}: {len(section.claims)} lines over max_claims {spec.max_claims}"
            )
        for title, lines in _role_blocks(section.claims, facts):
            if lines < spec.min_claims_per_role:
                violations.append(
                    f"{spec.name_en}: {title!r} has {lines} lines, "
                    f"under min_claims_per_role {spec.min_claims_per_role}"
                )
            if spec.max_claims_per_role is not None and lines > spec.max_claims_per_role:
                violations.append(
                    f"{spec.name_en}: {title!r} has {lines} lines, "
                    f"over max_claims_per_role {spec.max_claims_per_role}"
                )
        linked = {fact_id for claim in section.claims for fact_id in claim.fact_ids}
        dropped = [fact_id for fact_id in spec.pinned_fact_ids if fact_id not in linked]
        if dropped:
            violations.append(f"{spec.name_en}: pinned facts not kept: {', '.join(dropped)}")
    return violations


def _is_writer_wording(claim: ClaimLine) -> bool:
    if claim.claim_type == "reviewed":
        return True
    return claim.claim_type == "derived" and claim.derivation_id == EXTRACTIVE_DERIVATION[0]


def reworded_share(content: DraftDocument) -> float | None:
    """The share of evidence lines in wording the writer chose rather than the frame's.

    Tailoring is the product: a writer that keeps the right facts but echoes each
    canonical rendering unchanged has chosen, not tailored. The engine accepts the
    echo - it is always safe - so nothing else notices when a prompt change makes the
    writer fall back to it. Writer wording is a line the semantic review authorized
    (`reviewed`) or one the extractive derivation proved from its facts; canonical
    lines and the engine's own presentation templates are not.

    None when the document has no evidence line. A high share is not better without
    limit - the withheld rate is its counterweight - but a drop is a regression.
    """
    lines = evidence_lines(content)
    if not lines:
        return None
    return sum(1 for claim in lines if _is_writer_wording(claim)) / len(lines)


#: A quote shorter than this ("English", "SaaS") overlaps too many sentences to name one.
_MIN_OVERLAP = 12


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def requirements_quoting(analysis: JobAnalysis, passage: str) -> list[Requirement]:
    """The requirements read from `passage`: their quote or text overlaps it.

    A requirement overlaps when its source quote or its text lies within the
    passage, or the passage within it, compared case- and whitespace-insensitively;
    a fragment under `_MIN_OVERLAP` characters names no sentence and is ignored.
    Used to find what the analysis made of one known sentence of a posting.
    """
    target = _normalized(passage)
    if not target:
        return []
    found: list[Requirement] = []
    for requirement in analysis.requirements:
        candidates = [requirement.text]
        if requirement.source is not None:
            candidates.append(requirement.source.quote)
        for candidate in candidates:
            text = _normalized(candidate)
            if len(text) >= _MIN_OVERLAP and (text in target or target in text):
                found.append(requirement)
                break
    return found


def injection_requirements(analysis: JobAnalysis, injected: str) -> list[str]:
    """IDs of requirements the analysis made out of an instruction injected into the posting.

    The posting is untrusted input: an instruction inside it is text to read, not a
    demand of the employer and not an order to the model. A requirement whose quote
    or text is that instruction means the analysis treated it as content. The engine
    locates quotes but cannot judge whether a located sentence is a real demand, so
    this is the model's judgement and worth tracking. Empty is the right answer.
    """
    return [requirement.requirement_id for requirement in requirements_quoting(analysis, injected)]
