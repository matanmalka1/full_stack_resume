"""What an AI Proposal must survive before any of it becomes state.

Invariant 13 says AI output is a Proposal and deterministic policy decides what
becomes state. That is only true if the checks are the *same* ones a manual edit
passes, run in the same place. So nothing here re-implements support checking:
proposed wording goes through `apply_claim_edit`, exactly as a user's typed line
does, and this module reads the result.

The difference is what happens to a line that cannot be authorized. §14 saves a
user's unsupported free text as a `pending` claim, because the user is mid-edit
and their words are theirs. A provider is not mid-edit: an unsupported proposed
line is a wrong answer to a task, so none of its wording reaches the document.
It is withheld - the line keeps the wording it had before the Operation - and
listed, never silently dropped or quietly downgraded. Only a Proposal none of
whose lines survives is refused whole, as `ProposalRejected`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from ...domain.claim_review import (
    REVIEW_POLICY_VERSION,
    SHAPE_PROBLEMS,
    ReviewProblemCode,
    review_problems,
)
from ...domain.contracts.drafts import ClaimReviewAssertion, ClaimReviewEvidence, DraftDocument
from ...domain.contracts.knowledge import FactStatus
from ...domain.contracts.providers import (
    ClaimSupportProposal,
    ProposedClaim,
)
from ...domain.drafts import (
    apply_claim_edit,
    authorize_reviewed_claim,
    draft_claims,
)
from ...domain.facts import FactStore, FactStoreError
from ..errors import ClaimReviewUncertain, ClaimReviewUnsupported, ProposalRejected
from ..operations import ClaimReviewReason, ClaimReviewSource, RejectedClaimReview
from .ai_calls import RecordedCall


def fact_context(facts: FactStore, fact_ids: list[str], language: str) -> list[dict[str, object]]:
    """The minimal description of one fact a task needs to write about it.

    Meaning, rendering, tags, and the ID. Not provenance, not lifecycle status,
    not the source file - a task that does not need them cannot leak them, and
    architecture §11 gives each task minimal allowed context rather than the
    fact store.
    """
    context: list[dict[str, object]] = []
    for fact_id in fact_ids:
        try:
            fact = facts.get(fact_id, canonical_only=True)
        except ValueError:
            continue
        context.append(
            {
                "fact_id": fact.fact_id,
                "meaning": fact.meaning,
                "rendering": facts.rendering(fact.fact_id, language),
                "tags": list(fact.tags),
                "style": fact.resume_style,
            }
        )
    return context


def analysis_fact_context(facts: FactStore) -> list[dict[str, object]]:
    """Every canonical fact an extraction may cite, as little of it as possible.

    Meaning, tags, and the one structured numeric field a threshold can be
    traced to (`effective_dates`) - no renderings, because analysis writes no
    wording, and no provenance or lifecycle, for the reason `fact_context`
    gives. The pool is the whole canonical fact store rather than a Profile's
    allowed facts: which requirements the candidate meets is decided before
    and independently of which Profile presents them, exactly as
    `verify_and_cover_extraction` decides it against the whole store.
    """
    return [
        {
            "fact_id": fact.fact_id,
            "meaning": fact.meaning,
            "tags": list(fact.tags),
            "effective_dates": fact.effective_dates,
        }
        for fact in facts.facts.values()
        if fact.status is FactStatus.CANONICAL
    ]


Verdict = Literal["uncertain", "unsupported", "unattested", "refused"]


@dataclass(frozen=True)
class WithheldClaim:
    """One proposed line the engine did not authorize, and why.

    `text` and `fact_ids` are the refused proposal, not what the document holds:
    the document keeps the line as it was before the Operation. `detail` is the
    engine's own sentence for logs and the refusal message, never shown as-is.
    """

    claim_id: str
    text: str
    fact_ids: list[str]
    verdict: Verdict
    detail: str
    problems: list[ReviewProblemCode] = field(default_factory=list)
    rationale: str | None = None


def apply_proposed_claims(
    draft: DraftDocument,
    proposed: list[ProposedClaim],
    facts: FactStore,
    allowed: set[str],
    *,
    task: str,
) -> tuple[DraftDocument, list[WithheldClaim]]:
    """Apply proposed wording through the deterministic edit path, line by line.

    Each proposed line is applied with `apply_claim_edit`, which is the one
    authority on whether wording is canonical, derivable from its facts, or
    unsupported. A line the engine refuses - a fact outside the pool, no linked
    fact, wording the edit path rejects - is withheld: the draft keeps that line
    exactly as it was, and the refusal is returned with it. One bad line costs only
    itself: none of its content reaches the draft, and the lines beside it stand.

    A line that comes back `pending` goes on to semantic review. A claim ID the
    draft does not hold names no line, so it is ignored; a Proposal holding nothing
    but such IDs, or nothing at all, is refused whole. Whether enough survived to be
    worth writing is the caller's decision, after review.
    """
    if not proposed:
        raise ProposalRejected(f"{task} proposed no claims", unsupported=[])
    original = {claim.claim_id: claim for claim in draft_claims(draft)}
    unknown = sorted({str(claim.claim_id) for claim in proposed if claim.claim_id not in original})
    if len(unknown) == len({str(claim.claim_id) for claim in proposed}):
        raise ProposalRejected(
            f"{task} named claims that are not in this draft: {', '.join(unknown)}",
            unsupported=unknown,
        )

    updated = draft
    withheld: list[WithheldClaim] = []

    def withhold(claim: ProposedClaim, detail: str) -> None:
        withheld.append(
            WithheldClaim(
                claim_id=str(claim.claim_id),
                text=claim.text,
                fact_ids=list(claim.fact_ids),
                verdict="refused",
                detail=detail,
            )
        )

    for claim in proposed:
        if claim.claim_id not in original:
            continue
        outside = sorted(set(claim.fact_ids) - allowed)
        if outside:
            # Checked apart from support: a fact outside the pool that happens to
            # support the wording would pass `validate_derived_wording` and still be
            # a Profile violation - the plan and the Profile decide what this
            # document may contain, not the provider.
            withhold(claim, f"{task} named facts outside the allowed pool: {', '.join(outside)}")
            continue
        if not claim.fact_ids:
            withhold(claim, f"{task} proposed a claim with no supporting fact: {claim.claim_id}")
            continue
        current = next(line for line in draft_claims(updated) if line.claim_id == claim.claim_id)
        if (
            current.claim_type != "pending"
            and current == original[str(claim.claim_id)]
            and claim.text == current.text
            and list(claim.fact_ids) == current.fact_ids
        ):
            # Echoing an engine-composed line preserves its existing proof,
            # including presentation/composite contracts. Reclassifying the
            # same bytes as a free-text edit would discard that proof and
            # reject even an unchanged multi-fact line. Changed wording or
            # links must still pass the edit validator below.
            continue
        try:
            updated = apply_claim_edit(
                updated,
                str(claim.claim_id),
                list(claim.fact_ids),
                facts,
                text=claim.text,
            )
        except (KeyError, ValueError) as exc:
            withhold(claim, f"{task} proposed wording the engine refused: {exc}")

    return updated, withheld


def _review_sources(
    facts: FactStore, fact_ids: list[str], language: str
) -> list[ClaimReviewSource]:
    """The linked facts as read for this review; one no longer canonical is left out.

    A line refused for `stale-review-source` links a fact that cannot be read, and
    inventing its meaning would be worse than showing the facts that can be.
    """
    sources = []
    for fact_id in fact_ids:
        try:
            meaning = facts.get(fact_id, canonical_only=True).meaning
            rendering = facts.rendering(fact_id, language)
        except FactStoreError:
            continue
        sources.append(ClaimReviewSource(fact_id=fact_id, meaning=meaning, rendering=rendering))
    return sources


def review_semantically(
    draft: DraftDocument,
    review: RecordedCall[ClaimSupportProposal],
    facts: FactStore,
    claim_ids: set[str] | None = None,
) -> tuple[DraftDocument, list[WithheldClaim]]:
    """Authorize each pending claim whose review is complete, positive and source-attested.

    `claim_ids` narrows the review to the claims an Operation produced or was asked to
    review. Without it every pending claim in the draft is in scope, which made one
    unsupported line the user wrote elsewhere fail a regeneration it had no part in.

    Judged line by line. A claim the reviewer left out, or assessed more than once,
    has no usable evidence and is `unattested`; an assessment for a claim outside the
    scope attests nothing and is ignored. A line not authorized stays `pending` in the
    returned draft and is listed with its verdict - what happens to it is the
    caller's decision.
    """
    pending = {
        claim.claim_id: claim
        for claim in draft_claims(draft)
        if claim.claim_type == "pending" and (claim_ids is None or claim.claim_id in claim_ids)
    }
    proposal = review.proposal
    counted = Counter(item.claim_id for item in proposal.assessments)
    assessments = {item.claim_id: item for item in proposal.assessments}

    updated = draft
    withheld: list[WithheldClaim] = []
    for claim_id, claim in pending.items():

        def withhold(
            verdict: Verdict,
            detail: str,
            problems: list[ReviewProblemCode] | None = None,
            rationale: str | None = None,
            *,
            claim=claim,
        ) -> None:
            withheld.append(
                WithheldClaim(
                    claim_id=claim.claim_id,
                    text=claim.text,
                    fact_ids=list(claim.fact_ids),
                    verdict=verdict,
                    detail=detail,
                    problems=problems or [],
                    rationale=rationale,
                )
            )

        if counted[claim_id] != 1:
            withhold(
                "unattested",
                f"assess_claim_support assessed claim {claim_id} {counted[claim_id]} times",
                ["invalid-review-evidence"],
            )
            continue
        assessment = assessments[claim_id]
        rationale = assessment.rationale.strip() or None
        if assessment.verdict in ("uncertain", "unsupported"):
            withhold(
                assessment.verdict,
                f"semantic review found claim {claim_id} {assessment.verdict}",
                rationale=rationale,
            )
            continue
        problems: set[ReviewProblemCode] = {
            problem.code
            for problem in review_problems(
                claim_id=claim_id,
                text=claim.text,
                style=claim.style,
                fact_ids=claim.fact_ids,
                assertions=assessment.assertions,
                facts=facts,
                language=draft.language,
            )
        }
        if "unsupported-review-number" in problems and not problems & SHAPE_PROBLEMS:
            withhold(
                "unsupported",
                f"claim {claim_id} states a number its facts do not carry",
                rationale=rationale,
            )
            continue
        if problems:
            withhold(
                "unattested",
                f"semantic review did not authorize claim {claim_id}",
                sorted(problems),
                rationale,
            )
            continue
        updated = authorize_reviewed_claim(
            updated,
            claim_id,
            facts,
            ClaimReviewEvidence(
                policy_version=REVIEW_POLICY_VERSION,
                ai_call_id=review.ai_call_id,
                input_hash=review.record.input_hash,
                assertions=[
                    ClaimReviewAssertion(
                        claim_quote=item.claim_quote,
                        fact_ids=item.fact_ids,
                        source_quotes=item.source_quotes,
                    )
                    for item in assessment.assertions
                ],
            ),
        )
    return updated, withheld


def withheld_reason(
    draft: DraftDocument, withheld: list[WithheldClaim], facts: FactStore
) -> ClaimReviewReason:
    """The withheld lines as a client reads them, in document order.

    Captured from the exact in-memory draft and Knowledge the Operation used.
    Reconstructing from today's document or facts on a later GET would invent
    historical evidence. The reviewer's explanation is kept with its line: without it
    the user sees a near-identical sentence refused and cannot tell why.
    """
    by_id = {item.claim_id: item for item in withheld}
    placed: list[tuple[str, str | None, str]] = [
        (draft.headline.claim_id, None, "headline"),
        *((claim.claim_id, None, "contacts") for claim in draft.contacts),
    ]
    for section in draft.sections:
        heading = None
        for claim in section.claims:
            if claim.style == "heading":
                heading = claim.text
            placed.append((claim.claim_id, heading, section.name))
    return ClaimReviewReason(
        claims=[
            RejectedClaimReview(
                claim_id=claim_id,
                section=section,
                heading=heading,
                text=by_id[claim_id].text,
                verdict=by_id[claim_id].verdict,
                sources=_review_sources(facts, by_id[claim_id].fact_ids, draft.language),
                rationale=by_id[claim_id].rationale,
                problems=by_id[claim_id].problems,
            )
            for claim_id, heading, section in placed
            if claim_id in by_id
        ]
    )


def refusal(
    draft: DraftDocument, withheld: list[WithheldClaim], facts: FactStore
) -> ProposalRejected:
    """The one refusal for a Proposal none of whose lines was authorized.

    A reviewer's `unsupported` verdict outranks `uncertain`, which outranks a
    deterministic refusal: the code names the strongest finding, and the reason
    carries every line.
    """
    verdicts = {item.verdict for item in withheld}
    names = sorted(item.claim_id for item in withheld)
    error: ProposalRejected
    if "unsupported" in verdicts:
        error = ClaimReviewUnsupported(
            f"semantic review found unsupported claims: {', '.join(names)}", unsupported=names
        )
    elif "uncertain" in verdicts:
        error = ClaimReviewUncertain(
            f"semantic review was uncertain about claims: {', '.join(names)}", unsupported=names
        )
    else:
        error = ProposalRejected("; ".join(item.detail for item in withheld), unsupported=names)
    error.review_reason = withheld_reason(draft, withheld, facts)
    return error
