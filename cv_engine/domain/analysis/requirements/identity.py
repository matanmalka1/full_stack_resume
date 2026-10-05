"""Stable identities for requirements.

A requirement is identified by the posting it came from and its own normalized
words, under a stated version of this algorithm. Nothing about who read it, how
they were asked, or how they interpreted it is an input: a reworded prompt or a
different model reading the same sentence must produce the same requirement.
"""

from __future__ import annotations

import re

from ....util import canonical_json, sha256_text

_WHITESPACE = re.compile(r"\s+")


def normalize_span(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def requirement_id(
    *,
    normalized_hash: str,
    identity_version: str,
    identity_span: str,
    ordinal: int,
) -> str:
    """The id for one requirement's text in one posting.

    `identity_version` is the identity-algorithm version, not the prompt or task
    version; `job_text` is the normalized hash of the text the requirement was read
    from.
    """
    payload: dict[str, object] = {
        "job_text": normalized_hash,
        "identity_version": identity_version,
        "span": identity_span,
        "ordinal": ordinal,
    }
    return sha256_text(canonical_json(payload))[:16]
