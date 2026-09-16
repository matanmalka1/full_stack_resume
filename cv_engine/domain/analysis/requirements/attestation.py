"""The source gate: proof that a proposed requirement's quote was actually said.

Deterministic and cheap, and it proves exactly one thing - the text occurs in
the signed snapshot at the offsets claimed - never more. It is not an
injection defense: injected text sits inside the signed snapshot like any
other sentence, so it is quoted successfully too. See stage-1 plan §1.1 for
what actually is checked for injected instructions (a before/after meaning
comparison at the acceptance layer, not this gate).

Offsets are a pointer, not the claim. The claim is that the posting says this,
and the posting is the engine's own signed snapshot, so where the sentence sits
is a string search the engine performs exactly rather than a number it takes on
trust. A live model proved it cannot supply that number: it returned a 219-
character quote word for word and placed its start 137 characters from where the
posting actually says it. What it got right - the text - is the part that
matters.

So a claimed span is honoured when it holds, repaired when it misses by one
boundary character, and otherwise resolved by locating the provider's quote in
the source. Resolution requires exactly one occurrence, in the search scope the
caller names: two occurrences mean the engine would be choosing which sentence
the evidence points at, which is the guess this gate exists to refuse. The
returned attestation always names exact source text; interior differences are
never normalized or approximately matched, and a quote the source does not
carry at all is refused rather than located.

It is not an injection defense: injected text sits inside the signed snapshot
like any other sentence, so it is quoted successfully too. What is checked for
injected instructions is a before/after meaning comparison at the acceptance
layer, not this gate.
"""

from __future__ import annotations

from ...contracts.analysis import RequirementAttestation


class InvalidRequirementAttestation(ValueError):
    """One proposed requirement's attestation does not hold against source text.

    A domain-level refusal, not an application one: the application layer
    catches this and re-raises `ProviderInvalidOutput` so the failure reaches
    `OperationFailureCode.INVALID_OUTPUT` on the same route
    `refuse_facts_outside_the_pool` already uses for a fact outside the pool.
    """


class AmbiguousRequirementAttestation(InvalidRequirementAttestation):
    """The quote is in the source more than once and the offsets do not resolve it.

    Separate from its parent because it says something different about the
    provider. A quote the source never carries is a fabrication and voids the
    proposal that made it. A quote the source carries twice is the engine
    declining to choose between two real sentences, which is a limit of what
    can be established here rather than evidence of bad faith - and a condition
    that cannot be established stays explicit (product-spec section 2,
    "Semantic analysis authority") instead of being guessed either way.
    """


def reconcile_attestation(
    attestation: RequirementAttestation,
    *,
    source_text: str,
    scope: tuple[int, int] | None = None,
) -> RequirementAttestation:
    """Return an exact source attestation, repairing or locating the span.

    When the claimed source span adds one edge character to the quote, prefer
    that signed source slice. Otherwise find the provider's quote verbatim at a
    span whose start/end is at most one character from the claimed offsets. If
    neither works, accept the claimed span when the provider's quote adds one
    edge character. Failing all of those, locate the quote in `scope` - the
    whole source when the caller names none - and adopt that span when the
    quote occurs there exactly once.

    `scope` is what makes locating a member's quote safe. A member must sit
    inside its requirement's quote anyway, so searching that window answers
    "which of these sentences" for a phrase that repeats elsewhere in the
    posting, without ever reaching outside the region the member belongs to.

    In every repaired case the resulting quote and offsets point to exact
    source text.
    """
    start, end = attestation.start, attestation.end
    if not (0 <= start < end <= len(source_text)):
        # Out of bounds says the pointer is unusable, not that the quote is
        # false. The quote is still a claim about this source and is still
        # answerable by looking.
        return _locate(attestation.quote, source_text, scope=scope, claimed=(start, end))

    actual = source_text[start:end]
    if actual == attestation.quote:
        return attestation

    if attestation.quote in (actual[1:], actual[:-1]):
        return RequirementAttestation(quote=actual, start=start, end=end)

    nearby: list[tuple[int, int]] = []
    for candidate_start in range(max(0, start - 1), min(len(source_text), start + 1) + 1):
        for candidate_end in range(
            max(candidate_start + 1, end - 1),
            min(len(source_text), end + 1) + 1,
        ):
            if source_text[candidate_start:candidate_end] == attestation.quote:
                nearby.append((candidate_start, candidate_end))
    if len(nearby) == 1:
        corrected_start, corrected_end = nearby[0]
        return RequirementAttestation(
            quote=attestation.quote, start=corrected_start, end=corrected_end
        )

    if actual in (attestation.quote[1:], attestation.quote[:-1]):
        return RequirementAttestation(quote=actual, start=start, end=end)

    return _locate(attestation.quote, source_text, scope=scope, claimed=(start, end))


def _locate(
    quote: str,
    source_text: str,
    *,
    scope: tuple[int, int] | None,
    claimed: tuple[int, int],
) -> RequirementAttestation:
    """The span the source itself gives for this quote, when it gives exactly one.

    The search window is clamped to the source rather than trusted, because a
    scope derived from another unusable span is no more reliable than the span
    that produced it.
    """
    low, high = (0, len(source_text)) if scope is None else scope
    low = max(0, min(low, len(source_text)))
    high = max(low, min(high, len(source_text)))
    window = source_text[low:high]

    found: list[int] = []
    cursor = window.find(quote)
    while cursor != -1:
        found.append(low + cursor)
        cursor = window.find(quote, cursor + 1)

    if len(found) == 1:
        return RequirementAttestation(quote=quote, start=found[0], end=found[0] + len(quote))
    if not found:
        raise InvalidRequirementAttestation(
            f"attestation quote is not in the source: claimed source_text"
            f"[{claimed[0]}:{claimed[1]}], quote {quote!r}"
        )
    raise AmbiguousRequirementAttestation(
        f"attestation quote occurs {len(found)} times in the searched source and its "
        f"offsets do not resolve which: claimed source_text[{claimed[0]}:{claimed[1]}], "
        f"quote {quote!r}"
    )


def verify_attestation(attestation: RequirementAttestation, *, source_text: str) -> None:
    """Refuse an attestation whose quote is not exactly what the source says.

    Word for word, byte offsets, no normalization: no casefold, no strip, no
    whitespace collapsing. `source_text` must be the exact string the provider
    was given - the same string `read_snapshot` returned - not a normalized or
    re-encoded copy, or the comparison is against the wrong object entirely
    (stage-1 plan §5.6).
    """
    start, end = attestation.start, attestation.end
    if not (0 <= start < end <= len(source_text)):
        raise InvalidRequirementAttestation(
            f"attestation offsets [{start}, {end}) are out of bounds for a source of "
            f"length {len(source_text)}"
        )
    actual = source_text[start:end]
    if actual != attestation.quote:
        raise InvalidRequirementAttestation(
            f"attestation quote does not match source_text[{start}:{end}]: "
            f"expected {attestation.quote!r}, found {actual!r}"
        )
