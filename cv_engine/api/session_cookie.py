"""The one cookie that carries a session (architecture §18.4).

`__Host-` binds it to this origin: `Secure`, `Path=/`, and no `Domain`. Browsers treat
`http://localhost` and `http://127.0.0.1` as secure, so the same cookie works in
development. The token is never in a response body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request, Response

from ..application.accounts import SessionGrant

SESSION_COOKIE = "__Host-cv_session"


def _session_token(request: Request) -> str | None:
    """The cookie's value, or None: a missing session is the service's 401, not a 422."""
    return request.cookies.get(SESSION_COOKIE)


SessionToken = Annotated[str | None, Depends(_session_token)]


def set_session_cookie(response: Response, grant: SessionGrant) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        grant.token,
        expires=datetime.fromisoformat(grant.expires_at),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
