"""The one cookie that carries a session (architecture §18.4).

`__Host-` binds it to this origin: `Secure`, `Path=/`, and no `Domain`. Browsers treat
`http://localhost` and `http://127.0.0.1` as secure, so the same cookie works in
development. The token is never in a response body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request, Response

from ..application.accounts import SessionGrant, UserView
from ..application.actor import Actor
from .dependencies import Services

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


def require_session(services: Services, token: SessionToken) -> UserView:
    """Every route but sign-in and health: a valid session or `401 AUTHENTICATION_REQUIRED`."""
    return services.accounts.current_user(token)


def current_actor(user: Annotated[UserView, Depends(require_session)]) -> Actor:
    """Who the request acts for. FastAPI resolves `require_session` once per request, so
    the router-level check and this share one session lookup."""
    return Actor(user_id=user.id)


#: The signed-in user a route passes to every service call (architecture §18.3).
CurrentActor = Annotated[Actor, Depends(current_actor)]
