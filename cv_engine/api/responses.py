"""The one place an accepted Operation becomes a `202` with a `Location`.

Every asynchronous command in the slice - analyze, draft generation, section and
claim regeneration, AI plan proposal, render - returns the same thing: the
Operation the client is now to poll. Writing that in each router is how one of
them ends up returning `200`, or `202` with no `Location`, and a client that
polls one endpoint successfully then cannot poll another.

The helper sets the status itself rather than relying on the route's
`status_code`, because `POST /analyses/{id}/selection-plans` is specified as
`201` for deterministic mode and `202` for AI proposal mode: one route, two
statuses, decided per request.
"""

from __future__ import annotations

import string

from fastapi import Response, status
from fastapi.responses import StreamingResponse

from ..application.artifacts import ArtifactDelivery
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

    The name is already free of quotes, separators, and control characters when
    it gets here: `application.artifacts.safe_filename` guarantees that before
    the name reaches transport, so a filename cannot inject a second parameter.
    """
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii").replace("?", "_")
    return (
        f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{_percent_encode(filename)}"
    )


def artifact_response(delivery: ArtifactDelivery) -> StreamingResponse:
    """The one place a verified delivery becomes an HTTP response.

    Shared by the plain artifact download and the recruiter export so the two
    cannot drift into sending the same bytes under different headers - which is
    the same reason `accepted_operation` exists for `202`.

    `Content-Length` is the size the store measured *after* verifying the hash,
    so it describes the exact bytes being sent. The `ETag` is the registered
    content hash: an immutable payload's hash is a perfect validator, and a
    client that already holds it never needs the body again.
    """
    return StreamingResponse(
        delivery.stream.chunks(),
        media_type=delivery.media_type,
        headers={
            "Content-Disposition": content_disposition(delivery.filename),
            "Content-Length": str(delivery.size),
            "ETag": f'"{delivery.content_hash}"',
        },
    )


def inline_html_response(delivery: ArtifactDelivery) -> StreamingResponse:
    """Frame verified HTML without duplicating artifact verification or download policy."""
    return StreamingResponse(
        delivery.stream.chunks(),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Length": str(delivery.size),
            "ETag": f'"{delivery.content_hash}"',
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
