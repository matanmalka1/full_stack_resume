"""Stable identities for source-attested AI requirements."""

from __future__ import annotations

import re

from ....util import canonical_json, sha256_text
from ...contracts.analysis import MissingComponent, Requirement, RequirementInterpretation
from .concepts import RequirementConceptStore
from .segmentation import StatementLine, overlaps, requirement_lines

UNDETERMINED_INTERPRETATION = "undetermined-interpretation-v1"
_WHITESPACE = re.compile(r"\s+")


def normalize_span(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def interpretation_identity_key(interpretation: RequirementInterpretation) -> dict[str, object]:
    return {
        "source_role": interpretation.source_role,
        "obligation": interpretation.obligation,
        "composition": interpretation.composition,
        "members": sorted(
            normalize_span(member.attestation.quote) if member.attestation else member.label
            for member in interpretation.members
        ),
        "negation": interpretation.negation,
    }


def requirement_id(
    *,
    normalized_hash: str,
    extraction_version: str,
    identity_span: str,
    ordinal: int,
    interpretation: RequirementInterpretation | None = None,
    kind: str | None = None,
    demanded: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "snapshot": normalized_hash,
        "extractor": extraction_version,
        "span": identity_span,
        "ordinal": ordinal,
    }
    if interpretation is not None:
        payload["interpretation"] = interpretation_identity_key(interpretation)
    if kind is not None:
        payload["kind"] = kind
    if demanded is not None:
        payload["demanded"] = demanded
    return sha256_text(canonical_json(payload))[:16]


def undetermined_requirement(
    line: StatementLine,
    *,
    normalized_hash: str,
    extraction_version: str,
    ordinal: int,
) -> Requirement:
    return Requirement(
        requirement_id=requirement_id(
            normalized_hash=normalized_hash,
            extraction_version=f"{extraction_version}:{UNDETERMINED_INTERPRETATION}",
            identity_span=normalize_span(line.text),
            ordinal=ordinal,
        ),
        text=line.text,
        kind="presence",
        mandatory=False,
        coverage="undetermined",
        missing_components=[
            MissingComponent(component_id="unmapped-statement", label="Unmapped requirement")
        ],
    )


def unmatched_requirement_lines(
    text: str,
    concepts: RequirementConceptStore,
    mapped_spans: list[tuple[int, int]],
) -> list[StatementLine]:
    return [
        line
        for line in requirement_lines(text, concepts)
        if not any(overlaps((line.start, line.end), span) for span in mapped_spans)
    ]
