from __future__ import annotations

from ...application.settings import ExecutionMode, UiDensity, UiTextSize
from .health import HttpSchema


class SettingsResponse(HttpSchema):
    edit_version: int
    auto_generate_when_review_not_required: bool
    ai_enabled: bool
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode
    open_browser_on_launch: bool
    ui_density: UiDensity
    ui_text_size: UiTextSize
    provider_configured: bool
    updated_at: str | None = None


class UpdateSettingsRequest(HttpSchema):
    auto_generate_when_review_not_required: bool
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode
    open_browser_on_launch: bool
    ui_density: UiDensity
    ui_text_size: UiTextSize
