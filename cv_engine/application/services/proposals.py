"""What an AI Proposal must survive before any of it becomes state.

Invariant 13 says AI output is a Proposal and deterministic policy decides what
becomes state. That is only true if the checks are the *same* ones a manual edit
passes, run in the same place. So nothing here re-implements support checking:
proposed wording goes through `apply_claim_edit`, exactly as a user's typed line
does, and this module reads the result.

The difference is what happens to a line that cannot be authorized. §14 saves a
user's unsupported free text as a `pending` claim, because the user is mid-edit
and their words are theirs. A provider is not mid-edit: an unsupported proposed
line is a wrong answer to a task, and invariant 11 plus test-plan §6 require it
to fail rather than be silently dropped or quietly downgraded. `ProposalRejected`
is that refusal, and it names the claims that caused it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from ...domain.contracts.drafts import ClaimReviewEvidence, DraftDocument
from ...domain.contracts.knowledge import FactStatus
from ...domain.contracts.providers import (
    ClaimSupportProposal,
    ProposedClaim,
    ProviderTaskResult,
)
from ...domain.drafts import (
    EDITABLE_STYLES,
    apply_claim_edit,
    authorize_reviewed_claim,
    draft_claims,
)
from ...domain.facts import FactStore
from ..errors import ClaimReviewUncertain, ClaimReviewUnsupported, ProposalRejected
from ..ports import SnapshotPayload


@dataclass(frozen=True)
class ProviderEvidence:
    """One preserved provider response, before it is registered.

    The payload is on disk and the `ArtifactVersion` row exists: both are
    written in the execute phase, so a cancellation between execution and
    activation cannot leave a payload nothing points at. What is still open is
    *activation*, which the Operation output's `active` flag carries.

    Carried as one value so a caller cannot register the row for one response
    and the payload for another.
    """

    task: str
    artifact_version_id: str
    payload: SnapshotPayload
    provenance: ProviderTaskResult


@contextmanager
def evidence_attached(evidence: ProviderEvidence) -> Iterator[None]:
    """Carry the already-preserved response out with a refusal of its content.

    The payload is written before the Proposal is checked, because checking is
    what may reject it and the bytes are what a rejection is evidence of. If the
    check then refuses, the refusal has to name the payload - otherwise the file
    is on disk with no row pointing at it, which is exactly the orphan the
    filesystem-first order exists to make reconcilable rather than routine.
    """
    try:
        yield
    except ProposalRejected as exc:
        exc.evidence = evidence
        raise


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


def refuse_facts_outside_the_pool(
    proposed_fact_ids: set[str],
    allowed: set[str],
    *,
    task: str,
) -> None:
    """Refuse a Proposal that names a fact the task was not given.

    Checked separately from support validation because the two catch different
    mistakes. A fact outside the pool that happens to support the wording would
    pass `validate_derived_wording` and still be a Profile violation: the plan
    and the Profile decide what this document may contain, not the provider.
    """
    outside = sorted(proposed_fact_ids - allowed)
    if outside:
        raise ProposalRejected(
            f"{task} named facts outside the allowed pool: {', '.join(outside)}",
            unsupported=outside,
        )


def apply_proposed_claims(
    draft: DraftDocument,
    proposed: list[ProposedClaim],
    facts: FactStore,
    allowed: set[str],
    *,
    task: str,
    allow_semantic_review: bool = False,
) -> DraftDocument:
    """Apply proposed wording through the deterministic edit path, or refuse.

    Each proposed line is applied with `apply_claim_edit`, which is the one
    authority on whether wording is canonical, derivable from its facts, or
    unsupported. A line that comes back `pending` was not authorized, and the
    whole Proposal is refused: partially applying it would leave the draft
    holding some of an answer the engine rejected, and the user would have no
    way to tell which half.

    The refusal carries every unauthorized claim rather than the first, so one
    round trip reports the whole problem.
    """
    proposed_ids = {fact_id for claim in proposed for fact_id in claim.fact_ids}
    refuse_facts_outside_the_pool(proposed_ids, allowed, task=task)

    original = {claim.claim_id: claim for claim in draft_claims(draft)}
    known = set(original)
    unknown = sorted({str(claim.claim_id) for claim in proposed if claim.claim_id not in known})
    if unknown:
        raise ProposalRejected(
            f"{task} named claims that are not in this draft: {', '.join(unknown)}",
            unsupported=unknown,
        )
    if not proposed:
        raise ProposalRejected(f"{task} proposed no claims", unsupported=[])

    updated = draft
    for claim in proposed:
        if not claim.fact_ids:
            raise ProposalRejected(
                f"{task} proposed a claim with no supporting fact: {claim.claim_id}",
                unsupported=[str(claim.claim_id)],
            )
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
            raise ProposalRejected(
                f"{task} proposed wording the engine refused: {exc}",
                unsupported=[str(claim.claim_id)],
            ) from exc

    touched = {str(claim.claim_id) for claim in proposed}
    unsupported = sorted(
        line.claim_id
        for line in draft_claims(updated)
        if line.claim_id in touched and line.claim_type == "pending"
    )
    if unsupported and not allow_semantic_review:
        raise ProposalRejected(
            f"{task} proposed wording its facts do not support: {', '.join(unsupported)}",
            unsupported=unsupported,
        )
    return updated


def authorize_semantically_reviewed_claims(
    draft: DraftDocument,
    proposal: ClaimSupportProposal,
    facts: FactStore,
    evidence: ProviderEvidence,
) -> DraftDocument:
    """Apply only complete, positive, source-attested semantic review evidence."""
    pending = {
        claim.claim_id: claim for claim in draft_claims(draft) if claim.claim_type == "pending"
    }
    assessments = {item.claim_id: item for item in proposal.assessments}
    if len(assessments) != len(proposal.assessments) or set(assessments) != set(pending):
        missing = sorted(set(pending) - set(assessments))
        extra = sorted(set(assessments) - set(pending))
        raise ProposalRejected(
            "assess_claim_support did not cover the exact pending claims; "
            f"missing={missing}, extra={extra}",
            unsupported=missing + extra,
        )

    updated = draft
    refused: list[str] = []
    uncertain: list[str] = []
    unsupported: list[str] = []
    for claim_id, claim in pending.items():
        assessment = assessments[claim_id]
        if assessment.verdict == "uncertain":
            uncertain.append(claim_id)
            continue
        if assessment.verdict == "unsupported":
            unsupported.append(claim_id)
            continue
        if claim.style not in EDITABLE_STYLES or not assessment.assertions:
            refused.append(claim_id)
            continue
        joined_claim_quotes = "".join(item.claim_quote for item in assessment.assertions)

        def normalize(value: str) -> str:
            return "".join(char.casefold() for char in value if char.isalnum())

        if normalize(joined_claim_quotes) != normalize(claim.text):
            refused.append(claim_id)
            continue
        cited: set[str] = set()
        valid = True
        for assertion in assessment.assertions:
            if not assertion.claim_quote or assertion.claim_quote not in claim.text:
                valid = False
                break
            cited.update(assertion.fact_ids)
            if len(assertion.source_quotes) != len(assertion.fact_ids):
                valid = False
                break
            try:
                for fact_id, quote in zip(assertion.fact_ids, assertion.source_quotes, strict=True):
                    if fact_id not in claim.fact_ids:
                        valid = False
                        break
                    fact = facts.get(fact_id, canonical_only=True)
                    sources = [fact.meaning, facts.rendering(fact_id, draft.language)]
                    if quote not in sources[0] and quote not in sources[1]:
                        valid = False
                        break
            except ValueError:
                valid = False
                break
        source_text = " ".join(
            " ".join(
                (
                    facts.get(fact_id, canonical_only=True).meaning,
                    facts.rendering(fact_id, draft.language),
                )
            )
            for fact_id in claim.fact_ids
        )

        def protected(value: str) -> set[str]:
            return set(re.findall(r"\d+(?:[.,]\d+)?%?", value))

        if cited != set(claim.fact_ids):
            valid = False
        if protected(claim.text) - protected(source_text):
            unsupported.append(claim_id)
            continue
        if not valid:
            refused.append(claim_id)
            continue
        updated = authorize_reviewed_claim(
            updated,
            claim_id,
            facts,
            ClaimReviewEvidence(
                policy_version="semantic-claim-support-v1",
                provider_artifact_version_id=evidence.artifact_version_id,
                input_hash=evidence.provenance.input_hash,
                assertions=[item.model_dump(mode="json") for item in assessment.assertions],
            ),
        )
    if unsupported:
        raise ClaimReviewUnsupported(
            f"semantic review found unsupported claims: {', '.join(sorted(unsupported))}",
            unsupported=sorted(unsupported),
        )
    if uncertain:
        raise ClaimReviewUncertain(
            f"semantic review was uncertain about claims: {', '.join(sorted(uncertain))}",
            unsupported=sorted(uncertain),
        )
    if refused:
        raise ProposalRejected(
            f"semantic review did not authorize claims: {', '.join(sorted(refused))}",
            unsupported=sorted(refused),
        )
    return updated
