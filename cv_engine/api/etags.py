"""The WorkingDraft ETag: one spelling, and one place that parses it.

An ETag has to identify the exact content a client was editing, so it carries
both halves of the optimistic token: the `edit_version` proves nobody has saved
since, and the `content_hash` proves the client was looking at this document
rather than at another draft that happens to be at the same version.

Formatting is transport, which is why it lives here rather than in the
application layer: the command takes an integer and a hash, and how those are
spelled inside a header is HTTP's business. Parsing refuses rather than guesses
- a malformed `If-Match` is a request the server cannot honour, not a request
it should honour approximately.
"""

from __future__ import annotations

from typing import Annotated, NamedTuple

from fastapi import Header

from ..application.errors import PreconditionFailed


class DraftToken(NamedTuple):
    edit_version: int
    content_hash: str


def draft_etag(edit_version: int, content_hash: str) -> str:
    """The strong validator for one exact WorkingDraft version."""
    return f'"{edit_version}-{content_hash}"'


def parse_draft_etag(value: str) -> DraftToken:
    """The version and hash inside one `If-Match` value.

    `*` is refused deliberately. It means "any current representation", and a
    save that matched anything would be exactly the lost update `If-Match`
    exists to prevent.
    """
    candidate = value.strip()
    if candidate.startswith("W/"):
        raise PreconditionFailed(
            "a weak ETag cannot authorize a working draft save; send the exact "
            "ETag the read returned"
        )
    candidate = candidate.strip('"')
    version, separator, content_hash = candidate.partition("-")
    if not separator or not content_hash or not version.isdigit():
        raise PreconditionFailed("If-Match must be the ETag a working draft read returned")
    return DraftToken(edit_version=int(version), content_hash=content_hash)


IfMatch = Annotated[
    str,
    Header(
        alias="If-Match",
        description=(
            "Required. The ETag returned by the matching working-draft read. A "
            "value that no longer describes the stored draft is a 409 and "
            "changes nothing."
        ),
    ),
]
