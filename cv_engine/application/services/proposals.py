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

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from ...domain.drafts import apply_claim_edit, draft_claims
from ...domain.facts import FactStore
from ...domain.models import DraftDocument, Profile, ProposedClaim, ProviderTaskResult
from ..errors import ProposalRejected
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


def allowed_fact_pool(profile: Profile) -> set[str]:
    """Every fact this Profile is allowed to say, across all of its sections.

    The pool, not the fact store. A provider is given this set as context and is
    checked against the same set afterwards, so a fact it never saw cannot enter
    a document by being named in an answer.
    """
    return {fact_id for section in profile.sections for fact_id in section.fact_ids}


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

    known = {claim.claim_id for claim in draft_claims(draft)}
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
    if unsupported:
        raise ProposalRejected(
            f"{task} proposed wording its facts do not support: {', '.join(unsupported)}",
            unsupported=unsupported,
        )
    return updated
