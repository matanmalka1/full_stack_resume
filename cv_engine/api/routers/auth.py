from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from ..client_address import client_ip
from ..dependencies import Services
from ..problems import RATE_LIMITED_OPENAPI_RESPONSE
from ..schemas.auth import ChangePasswordRequest, LoginRequest, MeResponse
from ..session_cookie import SessionToken, clear_session_cookie, set_session_cookie


def _no_store(response: Response) -> None:
    """Who is signed in is never cached, by the browser or anything between."""
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(_no_store)])


def _empty() -> Response:
    # A route that builds its own Response does not get the dependency's headers.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post(
    "/login",
    response_model=MeResponse,
    summary="Sign in and start a session",
    responses={429: RATE_LIMITED_OPENAPI_RESPONSE},
)
def login(
    request: LoginRequest,
    services: Services,
    token: SessionToken,
    response: Response,
    http_request: Request,
) -> MeResponse:
    grant = services.accounts.login(
        request.email,
        request.password,
        client_ip=client_ip(http_request, services.limits.trusted_proxy_hops),
        presented_token=token,
    )
    set_session_cookie(response, grant)
    return MeResponse.model_validate(grant.user.model_dump(mode="json"))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End the current session, if there is one, and clear its cookie",
)
def logout(services: Services, token: SessionToken) -> Response:
    services.accounts.logout(token)
    response = _empty()
    clear_session_cookie(response)
    return response


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End every session of the user, this one included",
)
def logout_all(services: Services, token: SessionToken) -> Response:
    services.accounts.logout_all(token)
    response = _empty()
    clear_session_cookie(response)
    return response


@router.get("/me", response_model=MeResponse, summary="The signed-in user")
def me(services: Services, token: SessionToken) -> MeResponse:
    return MeResponse.model_validate(services.accounts.current_user(token).model_dump(mode="json"))


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the password, end every other session, and rotate this one",
)
def change_password(
    request: ChangePasswordRequest, services: Services, token: SessionToken
) -> Response:
    grant = services.accounts.change_password(token, request.current_password, request.new_password)
    response = _empty()
    set_session_cookie(response, grant)
    return response
