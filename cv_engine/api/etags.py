"""The document and settings ETags: one spelling each, and one place that parses them.

The document's ETag is its `document_hash`, which already identifies the exact
content a client was editing. The settings ETag is its edit version.

Formatting is transport, which is why it lives here rather than in the
application layer: the command takes an integer and a hash, and how those are
spelled inside a header is HTTP's business. Parsing refuses rather than guesses
- a malformed `If-Match` is a request the server cannot honour, not a request
it should honour approximately.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

from ..application.errors import PreconditionFailed


def settings_etag(edit_version: int) -> str:
    return f'"settings-{edit_version}"'


def parse_settings_etag(value: str) -> int:
    candidate = value.strip().strip('"')
    prefix, separator, version = candidate.partition("-")
    if prefix != "settings" or not separator or not version.isdigit():
        raise PreconditionFailed("If-Match must be the ETag returned by the settings read")
    return int(version)


SettingsIfMatch = Annotated[
    str,
    Header(
        alias="If-Match",
        description="Required. The ETag returned by the matching settings read.",
    ),
]


def document_etag(document_hash: str) -> str:
    """The strong validator for one exact CV document: its `document_hash` (§21)."""
    return f'"{document_hash}"'


def parse_document_etag(value: str) -> str:
    """The `document_hash` inside one `If-Match` value; `*` and weak tags are refused."""
    candidate = value.strip()
    if candidate.startswith("W/"):
        raise PreconditionFailed(
            "a weak ETag cannot authorize a document save; send the exact ETag the read returned"
        )
    candidate = candidate.strip('"')
    if len(candidate) != 64 or any(character not in "0123456789abcdef" for character in candidate):
        raise PreconditionFailed("If-Match must be the ETag a document read returned")
    return candidate


DocumentIfMatch = Annotated[
    str,
    Header(
        alias="If-Match",
        description=(
            "Required. The ETag returned by the matching document read. A value that no "
            "longer describes the stored document is a 409 and changes nothing."
        ),
    ),
]
