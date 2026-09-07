"""The source gate: proof that a proposed requirement's quote was actually said.

Deterministic and cheap, and it proves exactly one thing - the text occurs in
the signed snapshot at the offsets claimed - never more. It is not an
injection defense: injected text sits inside the signed snapshot like any
other sentence, so it is quoted successfully too. See stage-1 plan §1.1 for
what actually is checked for injected instructions (a before/after meaning
comparison at the acceptance layer, not this gate).

One failure voids the whole proposed output. There is no silent repair and no
partial acceptance - `refuse_facts_outside_the_pool` in
`services/proposals.py` already refuses this way for a fact outside the pool,
and this is the same policy applied to a quote outside the source text.
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
