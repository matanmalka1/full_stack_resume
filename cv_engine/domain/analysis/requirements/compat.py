"""The one reader of a stored `Requirement`'s version-dependent fields.

`analysis_version` moved from "1.0" to "1.1" when the interpretation gate was
added. A record written under "1.0" never carried `interpretation`,
`attestation`, or `extractor` - Pydantic's field defaults would read it back
as `None` regardless, which is already the correct answer and is why there is
no version branch here today. This module exists anyway, as the single named
place policy code goes through, so that if a future migration ever needs to
compute a different answer for an old version, there is one place to put it
rather than a defaulted field silently doing the wrong thing everywhere it is
read directly.
"""

from __future__ import annotations

from ...contracts.analysis import Requirement, RequirementInterpretation


def interpretation_of(requirement: Requirement) -> RequirementInterpretation | None:
    """The interpretation this record carries, or `None` when it predates the gate.

    Policy code must call this rather than read `requirement.interpretation`
    directly: `None` means "cannot decide from interpretation" - not "assume a
    plain, unqualified requirement". A record that has no interpretation gets
    no interpretation-shaped default invented for it. What can be safely
    inferred already lives in a field the record actually carried:
    `requirement.mandatory` is that field for obligation, and it stays the
    authoritative signal regardless of what this function returns.
    """
    return requirement.interpretation
