from __future__ import annotations

from fastapi import APIRouter, Response

from ...application.settings import UpdateSettings
from ..dependencies import Services
from ..etags import SettingsIfMatch, parse_settings_etag, settings_etag
from ..schemas.settings import SettingsResponse, UpdateSettingsRequest
from ..session_cookie import CurrentActor

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Read the signed-in user's safe settings",
    responses={
        200: {
            "headers": {
                "ETag": {
                    "description": "Strong validator required by the next settings update.",
                    "schema": {"type": "string"},
                }
            }
        }
    },
)
def read_settings(services: Services, actor: CurrentActor, response: Response) -> SettingsResponse:
    result = services.settings.read(actor)
    response.headers["ETag"] = settings_etag(result.edit_version)
    return SettingsResponse.model_validate(result.model_dump(mode="json"))


@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update the signed-in user's safe settings",
    responses={
        200: {
            "headers": {
                "ETag": {
                    "description": "Strong validator required by the next settings update.",
                    "schema": {"type": "string"},
                }
            }
        }
    },
)
def update_settings(
    request: UpdateSettingsRequest,
    services: Services,
    actor: CurrentActor,
    response: Response,
    if_match: SettingsIfMatch,
) -> SettingsResponse:
    result = services.settings.update(
        actor,
        parse_settings_etag(if_match),
        UpdateSettings.model_validate(request.model_dump(mode="python")),
    )
    response.headers["ETag"] = settings_etag(result.edit_version)
    return SettingsResponse.model_validate(result.model_dump(mode="json"))
