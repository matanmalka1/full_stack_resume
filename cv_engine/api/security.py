"""Local security: body size, Origin, and CORS.

v2.0 has no authentication and no CSRF token. What stands in for them is that
the service is loopback-only, the UI is served same-origin, and every
state-changing request has to prove it came from an origin this instance
recognises.

Both middlewares are raw ASGI rather than `BaseHTTPMiddleware`, deliberately.
`BaseHTTPMiddleware` builds its own `Request`, and reading the body from it
consumes the receive channel: the route downstream then sees an empty body. The
body limit has to read the body to enforce itself, so it buffers and replays it
instead.

Both refuse before routing, so an oversize or foreign-origin request never
reaches a route - and a refusal is returned even for a path that does not
exist, rather than leaking which paths do.
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .problems import problem

#: Requests that cannot change state. Everything else must carry a known Origin.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

BODY_LIMIT_EXCEEDED = "BODY_LIMIT_EXCEEDED"
ORIGIN_NOT_ALLOWED = "ORIGIN_NOT_ALLOWED"


class BodySizeLimitMiddleware:
    """Refuse an oversize body with 413.

    `Content-Length` is checked first, which refuses an oversize request without
    reading it. It is only a claim, though, and a chunked request has none, so
    the body is also counted as it arrives and the same refusal fires if the
    claim was wrong or absent.

    Buffering the whole body is safe precisely because this middleware is what
    bounds it: nothing larger than the limit is ever held.
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self._max = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                if int(declared) > self._max:
                    await self._refuse(scope, send)
                    return
            except ValueError:
                response = problem(400, "INVALID_CONTENT_LENGTH", "Content-Length is not a number")
                await response(scope, receive, send)
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self._max:
                await self._refuse(scope, send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            """Hand the buffered body over once, then get out of the way.

            Everything after the replayed body must come from the real client
            channel. Returning a fabricated `http.disconnect` here instead is
            correct-looking and wrong: `StreamingResponse` runs
            `listen_for_disconnect(receive)` concurrently with the send loop and
            cancels the whole task group as soon as it sees a disconnect, so a
            synthetic one arrives immediately and kills the response before a
            single byte is written. A client then gets `200`, the right headers,
            and an empty body.

            No JSON response listens for disconnect, which is why this was
            invisible from Stage A until the first streaming route existed.
            """
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)

    async def _refuse(self, scope: Scope, send: Send) -> None:
        response = problem(
            413,
            BODY_LIMIT_EXCEEDED,
            f"Request body exceeds the configured limit of {self._max} bytes.",
            context={"max_body_bytes": self._max},
        )
        await response(scope, _no_more_body, send)


class OriginPolicyMiddleware:
    """Every mutation must come from an origin this instance recognises.

    A missing Origin is refused rather than allowed. A browser sends one on
    every cross-origin request and on same-origin non-GET requests, so a
    mutation without an Origin is not the browser case this product serves.

    `allowed` is the same-origin set plus, in development only, the single
    configured Vite origin. There is no wildcard, and no way to configure a list.
    """

    def __init__(self, app: ASGIApp, allowed: frozenset[str]) -> None:
        self.app = app
        self._allowed = allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "") in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        origin = Headers(scope=scope).get("origin")
        if origin is None:
            response = problem(
                403,
                ORIGIN_NOT_ALLOWED,
                "A state-changing request must carry an Origin header.",
            )
        elif origin not in self._allowed:
            # The rejected value is deliberately not echoed back.
            response = problem(403, ORIGIN_NOT_ALLOWED, "Origin is not allowed for this instance.")
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)


async def _no_more_body() -> Message:
    return {"type": "http.disconnect"}


def allowed_origins(host: str, port: int, dev_origin: str | None) -> frozenset[str]:
    """The exact origins this instance answers to.

    Both loopback spellings are included because the browser treats
    `127.0.0.1` and `localhost` as different origins and either may be what the
    user typed.
    """
    origins = {
        f"http://{host}:{port}",
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    }
    if dev_origin:
        origins.add(dev_origin)
    return frozenset(origins)
