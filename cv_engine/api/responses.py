"""The one place an accepted Operation becomes a `202` with a `Location`.

Every asynchronous command in the slice - analyze, draft generation, section and
claim regeneration, AI plan proposal, render - returns the same thing: the
Operation the client is now to poll. Writing that in each router is how one of
them ends up returning `200`, or `202` with no `Location`, and a client that
polls one endpoint successfully then cannot poll another.
"""

from __future__ import annotations

import string

from fastapi import Response, status

from ..application.operations import OperationView
from .schemas.operations import OperationResponse
from .versioning import API_PREFIX


def operation_location(operation_id: str) -> str:
    """Where an accepted Operation is polled. One spelling, one route."""
    return f"{API_PREFIX}/operations/{operation_id}"


def operation_response(operation: OperationView) -> OperationResponse:
    """The one mapping from the application view to the HTTP representation."""
    return OperationResponse.model_validate(operation.model_dump(mode="json"))


def accepted_operation(response: Response, operation: OperationView) -> OperationResponse:
    """`202 Accepted` plus the `Location` of the Operation to poll (§21, §22).

    The body is the same representation `GET /operations/{id}` returns, so a
    client can render progress from the acceptance response without a second
    request, and the `Location` is what it polls from then on.
    """
    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Location"] = operation_location(operation.id)
    return operation_response(operation)


#: RFC 3986 unreserved characters. Deliberately narrower than RFC 8187's
#: `attr-char`: over-encoding an `ext-value` is always valid, under-encoding is
#: not, and a narrow set has no edge cases to get wrong.
_UNRESERVED = frozenset(string.ascii_letters + string.digits + "-._~")


def _percent_encode(value: str) -> str:
    return "".join(
        character
        if character in _UNRESERVED
        else "".join(f"%{byte:02X}" for byte in character.encode("utf-8"))
        for character in value
    )


def content_disposition(filename: str) -> str:
    """`Content-Disposition` for one download, in both spellings a browser reads.

    The candidate's filename may legitimately be Hebrew - `filename_language`
    is `en` or `he` - and a bare `filename="..."` is defined over ASCII only, so
    a non-Latin name would arrive mangled or dropped. RFC 6266 answers this with
    two parameters: `filename` as an ASCII fallback and `filename*` as the
    percent-encoded UTF-8 truth, with clients preferring the second.

    Encoded here rather than with `urllib.parse.quote` because `urllib` is
    forbidden inside `api` by the layer guard. The rule is aimed at provider
    HTTP rather than at string escaping, but a guard that gets an exemption the
    first time it is inconvenient stops being a guard - and the replacement is
    ten lines with no network in them.

    The name comes from the renderer's recruiter filename (`filename_for`); this
    function does not sanitize it further.
    """
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii").replace("?", "_")
    return (
        f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{_percent_encode(filename)}"
    )
