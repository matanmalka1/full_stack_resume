"""The interpretation gate: policy checks on a provider's declared reading.

The source gate (`attestation.py`) proves a quote was said. It says nothing
about what the quote *means* - `mandatory` is a claim about the world, not a
transcription, and a provider's claim about it is policy-checked here the way
`refuse_facts_outside_the_pool` policy-checks a Proposal's fact ids.

A rejection here is total, like the source gate: `InvalidRequirementInterpretation`
voids the one requirement it names. There is no silent downgrade to a
different interpretation - see stage-1 plan §3.2.
"""

from __future__ import annotations

from ...contracts.analysis import RequirementAttestation, RequirementInterpretation
from .attestation import InvalidRequirementAttestation, verify_attestation
from .concepts import RequirementConceptStore
from .segmentation import _segments, _Span


class InvalidRequirementInterpretation(ValueError):
    """One proposed requirement's interpretation fails a policy check.

    Domain-level, like `InvalidRequirementAttestation`: the application layer
    re-raises this as `ProviderInvalidOutput` so it reaches
    `OperationFailureCode.INVALID_OUTPUT`.
    """


def verify_interpretation(
    interpretation: RequirementInterpretation,
    *,
    source_text: str,
    concepts: RequirementConceptStore,
    requirement_span: tuple[int, int] | None = None,
) -> None:
    """Refuse an interpretation the policy will not accept, before it is trusted.

    Source structure constrains the proposed obligation independently of the
    provider's context. `context_quote` is verified before any rule reads it
    as evidence for a mandatory marker.

    `requirement_span` is the requirement's own attestation offsets. When
    given, `context_quote` must fall in the *same posting statement* as the
    requirement it is meant to give context for - the same segmentation the
    rest of this package uses (`segmentation.py::_segments`), so a heading or
    the requirement's own sentence both qualify but an unrelated bullet
    elsewhere in the posting does not. Without this, a provider could quote a
    real mandatory marker from an unrelated sentence to fraudulently justify
    `mandatory` on a requirement whose own text never says so.

    The source-structure check below reads the requirement's *home* statement:
    the one it overlaps most. It used to demand containment, and a quote
    spanning two bullets matched no statement, fell out of the loop, and was
    never checked at all - so the gate was silently skipped by exactly the
    quote that most needed it, while `_same_statement` answered the same
    "which statement is this in" question by overlap two functions away (A7).
    Both now rest on one overlap primitive so they cannot drift apart again.

    Overlap rather than containment, and one home statement rather than every
    statement touched, are both deliberate. A crossing quote is not proof of
    bad faith: the prompt asks for the requirement verbatim and never promised
    that a requirement lies inside one statement, so refusing it outright
    would be a new rejection the provider was never told about. Testing it
    against *every* statement it touches would be stricter still - a quote
    reaching into a neighbouring "preferred" bullet would block a `mandatory`
    reading the requirement's own bullet supports.
    """
    if requirement_span is not None:
        start, end = requirement_span
        statement = _home_statement(requirement_span, source_text, concepts)
        if statement is not None:
            quoted = source_text[start:end].casefold()
            preferred = statement.section == "preferred" or any(
                marker in quoted for marker in concepts.preferred_markers
            )
            mandatory = not preferred and (
                statement.section == "requirements"
                or any(marker in quoted for marker in concepts.mandatory_markers)
            )
            if mandatory and (
                interpretation.source_role != "requirement"
                or interpretation.obligation != "mandatory"
            ):
                raise InvalidRequirementInterpretation(
                    "interpretation contradicts the source's explicit mandatory requirement"
                )
            if preferred and interpretation.obligation == "mandatory":
                raise InvalidRequirementInterpretation(
                    "interpretation strengthens an explicit preferred requirement"
                )

    if interpretation.context_quote is not None:
        if not interpretation.context_quote:
            raise InvalidRequirementInterpretation("context_quote must not be empty when present")
        _verify_context_quote_occurs(
            interpretation.context_quote,
            source_text,
            requirement_span=requirement_span,
            concepts=concepts,
        )

    if interpretation.obligation == "mandatory" and interpretation.source_role != "requirement":
        marked = interpretation.context_quote is not None and any(
            marker in interpretation.context_quote.casefold()
            for marker in concepts.mandatory_markers
        )
        if not marked:
            raise InvalidRequirementInterpretation(
                "obligation 'mandatory' requires source_role 'requirement', or a quoted "
                "mandatory marker in context_quote"
            )

    if interpretation.composition == "single":
        if interpretation.members:
            raise InvalidRequirementInterpretation("composition 'single' must not declare members")
    else:
        if len(interpretation.members) < 2:
            raise InvalidRequirementInterpretation(
                f"composition {interpretation.composition!r} requires at least two members"
            )
        # A member's `label` is a provider's description, not proof; only an
        # attested member can be mapped to a concept for coverage at all
        # (stage-1 plan §3.5a addendum). Verifying it here, at the same gate
        # that verifies the requirement's own quote, keeps "how do we know
        # this member is real" answered in exactly one place.
        for member in interpretation.members:
            if member.attestation is not None:
                try:
                    verify_attestation(member.attestation, source_text=source_text)
                    if requirement_span is not None and not (
                        requirement_span[0]
                        <= member.attestation.start
                        < member.attestation.end
                        <= requirement_span[1]
                    ):
                        raise InvalidRequirementInterpretation(
                            "member attestation must be contained in its requirement quote"
                        )
                except InvalidRequirementAttestation as exc:
                    raise InvalidRequirementInterpretation(
                        f"member {member.member_id!r} attestation is invalid: {exc}"
                    ) from exc


def _verify_context_quote_occurs(
    quote: str,
    source_text: str,
    *,
    requirement_span: tuple[int, int] | None,
    concepts: RequirementConceptStore,
) -> None:
    """`context_quote` is a claimed quote too, verified the same way as the main one.

    Reuses the source gate rather than a second string search: a
    `context_quote` is exactly as much a quote-of-source-text claim as the
    requirement's own attestation, and it deserves the identical exact-match
    proof, not a looser `in` check that would accept a paraphrase.

    A quote occurring more than once is refused rather than matched at its
    first occurrence: silently picking one location would let a same-statement
    check against the wrong occurrence pass by accident.
    """
    first = source_text.find(quote)
    if first == -1:
        raise InvalidRequirementInterpretation(
            f"context_quote is not found verbatim in the source text: {quote!r}"
        )
    if source_text.find(quote, first + 1) != -1:
        raise InvalidRequirementInterpretation(
            f"context_quote occurs more than once in the source text: {quote!r}"
        )
    try:
        verify_attestation(
            RequirementAttestation(quote=quote, start=first, end=first + len(quote)),
            source_text=source_text,
        )
    except InvalidRequirementAttestation as exc:
        raise InvalidRequirementInterpretation(str(exc)) from exc

    if requirement_span is not None and not _same_statement(
        (first, first + len(quote)), requirement_span, source_text, concepts
    ):
        raise InvalidRequirementInterpretation(
            "context_quote is not in the same statement as the requirement it is meant "
            "to give context for; a quote from elsewhere in the posting cannot justify "
            "this requirement's interpretation"
        )


def _overlap(span: tuple[int, int], statement_start: int, statement_end: int) -> int:
    """How many characters a span and a statement share; 0 or less means neither.

    The single definition of "this span is in that statement", used by both
    questions this module asks - which statement a requirement belongs to, and
    whether a context quote belongs to the same one. They were two different
    definitions (containment here, overlap there) for one question, which is
    what let a crossing quote skip the source-structure check entirely (A7).
    """
    return min(span[1], statement_end) - max(span[0], statement_start)


def _home_statement(
    span: tuple[int, int], source_text: str, concepts: RequirementConceptStore
) -> _Span | None:
    """The statement a span most belongs to, or `None` if it touches none.

    Most-overlap rather than first-overlap: a quote that runs a few characters
    into the next bullet belongs to the bullet it is mostly in, and reading it
    against the neighbour it barely touches would judge the requirement by
    wording that is not its own. Ties fall to the earlier statement, which is
    the order `_segments` yields and the order the posting reads in.

    `None` means no statement covers that region of the posting at all. That is
    the segmenter not modelling the text (`A1`), not a claim about the
    proposal, so the caller skips the check rather than rejecting on it.
    """
    overlapping = [
        statement
        for statement in _segments(source_text, concepts)
        if _overlap(span, statement.start, statement.end) > 0
    ]
    if not overlapping:
        return None
    return max(overlapping, key=lambda statement: _overlap(span, statement.start, statement.end))


def _same_statement(
    quote_span: tuple[int, int],
    requirement_span: tuple[int, int],
    source_text: str,
    concepts: RequirementConceptStore,
) -> bool:
    """Whether both spans fall inside the same posting statement.

    Uses the engine's own statement segmentation (`segmentation.py::_segments`)
    rather than a character-distance heuristic: "nearby" is not well-defined
    across a posting's varied formatting, but "the same bullet, heading, or
    sentence" is exactly what the segmenter already decides for every other
    purpose in this package.

    Any shared statement counts, not the requirement's home statement alone: a
    context quote is offered as context, so a heading above the requirement's
    own bullet is exactly what it should be allowed to be, and narrowing this
    to the home statement would reject the legitimate case the parameter
    exists for.
    """
    return any(
        _overlap(quote_span, statement.start, statement.end) > 0
        and _overlap(requirement_span, statement.start, statement.end) > 0
        for statement in _segments(source_text, concepts)
    )
