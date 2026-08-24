from __future__ import annotations

from fastapi import APIRouter, Response

from ...application.settings import UpdateSettings
from ..dependencies import Services
from ..etags import SettingsIfMatch, parse_settings_etag, settings_etag
from ..schemas.settings import SettingsResponse, UpdateSettingsRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse, summary="Read safe Workspace settings")
def read_settings(services: Services, response: Response) -> SettingsResponse:
    result = services.settings.read()
    response.headers["ETag"] = settings_etag(result.edit_version)
    return SettingsResponse.model_validate(result.model_dump(mode="json"))


@router.patch("", response_model=SettingsResponse, summary="Update safe Workspace settings")
def update_settings(
    request: UpdateSettingsRequest,
    services: Services,
    response: Response,
    if_match: SettingsIfMatch,
) -> SettingsResponse:
    result = services.settings.update(
        parse_settings_etag(if_match),
        UpdateSettings.model_validate(request.model_dump(mode="python")),
    )
    response.headers["ETag"] = settings_etag(result.edit_version)
    return SettingsResponse.model_validate(result.model_dump(mode="json"))
