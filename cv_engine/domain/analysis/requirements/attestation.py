"""The source gate: proof that a proposed requirement's quote was actually said.

Deterministic and cheap, and it proves exactly one thing - the text occurs in
the signed snapshot at the offsets claimed - never more. It is not an
injection defense: injected text sits inside the signed snapshot like any
other sentence, so it is quoted successfully too. See stage-1 plan §1.1 for
what actually is checked for injected instructions (a before/after meaning
comparison at the acceptance layer, not this gate).

The provider may miss one boundary character.  That mechanical discrepancy is
reconciled only when the quote occurs verbatim one character from the claimed
span, or when the claimed span differs by one character at either edge. The
returned attestation always names exact source text; interior differences are
never normalized or approximately matched.
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


def reconcile_attestation(
    attestation: RequirementAttestation, *, source_text: str
) -> RequirementAttestation:
    """Return an exact source attestation after a narrowly bounded repair.

    When the claimed source span adds one edge character to the quote, prefer
    that signed source slice. Otherwise find the provider's quote
    verbatim at a span whose start/end is at most one character from the
    claimed offsets. If neither works, accept the claimed span only when the
    provider's quote adds one edge character. In every repaired case the
    resulting quote and offsets point to exact source text.
    """
    start, end = attestation.start, attestation.end
    if not (0 <= start < end <= len(source_text)):
        raise InvalidRequirementAttestation(
            f"attestation offsets [{start}, {end}) are out of bounds for a source of "
            f"length {len(source_text)}"
        )

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

    raise InvalidRequirementAttestation(
        f"attestation quote does not match source_text[{start}:{end}]: "
        f"expected {attestation.quote!r}, found {actual!r}"
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
