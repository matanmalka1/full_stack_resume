from __future__ import annotations

from fastapi import APIRouter, Response, status

from ..dependencies import Services
from ..schemas.auth import ChangePasswordRequest, LoginRequest, MeResponse
from ..session_cookie import SessionToken, clear_session_cookie, set_session_cookie

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeResponse, summary="Sign in and start a session")
def login(request: LoginRequest, services: Services, response: Response) -> MeResponse:
    grant = services.accounts.login(request.email, request.password)
    set_session_cookie(response, grant)
    return MeResponse.model_validate(grant.user.model_dump(mode="json"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="End the current session")
def logout(services: Services, token: SessionToken) -> Response:
    services.accounts.logout(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End every session of the user, this one included",
)
def logout_all(services: Services, token: SessionToken) -> Response:
    services.accounts.logout_all(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
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
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_session_cookie(response, grant)
    return response
