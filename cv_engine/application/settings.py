"""Safe, mutable Workspace settings exposed to the local Web client."""

from __future__ import annotations

from typing import Literal, Protocol

from .commands import BoundaryDTO
from .errors import PreconditionFailed, StateConflict


ExecutionMode = Literal["deterministic", "ai"]
UiDensity = Literal["comfortable", "compact"]
UiTextSize = Literal["normal", "large"]


class StoredSettings(BoundaryDTO):
    edit_version: int = 0
    auto_generate_when_review_not_required: bool = False
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode = "deterministic"
    open_browser_on_launch: bool = True
    ui_density: UiDensity = "comfortable"
    ui_text_size: UiTextSize = "normal"
    updated_at: str | None = None


class SettingsView(BoundaryDTO):
    edit_version: int
    auto_generate_when_review_not_required: bool
    ai_enabled: bool
    ai_enabled_override: bool | None
    default_execution_mode: ExecutionMode
    open_browser_on_launch: bool
    ui_density: UiDensity
    ui_text_size: UiTextSize
    provider_configured: bool
    updated_at: str | None = None


class UpdateSettings(BoundaryDTO):
    auto_generate_when_review_not_required: bool
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode
    open_browser_on_launch: bool
    ui_density: UiDensity
    ui_text_size: UiTextSize


class SettingsRepository(Protocol):
    def workspace_settings(self) -> StoredSettings: ...

    def update_workspace_settings(
        self, expected_edit_version: int, settings: UpdateSettings
    ) -> StoredSettings: ...


class SettingsService:
    def __init__(self, repository: SettingsRepository, *, provider_configured: bool):
        self.repo = repository
        self.provider_configured = provider_configured

    def _view(self, stored: StoredSettings) -> SettingsView:
        enabled = (
            self.provider_configured
            if stored.ai_enabled_override is None
            else stored.ai_enabled_override
        )
        return SettingsView(
            **stored.model_dump(mode="python"),
            ai_enabled=enabled,
            provider_configured=self.provider_configured,
        )

    def read(self) -> SettingsView:
        return self._view(self.repo.workspace_settings())

    def update(self, expected_edit_version: int, command: UpdateSettings) -> SettingsView:
        enabled = (
            self.provider_configured
            if command.ai_enabled_override is None
            else command.ai_enabled_override
        )
        if command.default_execution_mode == "ai" and not (
            self.provider_configured and enabled
        ):
            raise PreconditionFailed(
                "AI cannot be the default execution mode until it is enabled and configured"
            )
        try:
            stored = self.repo.update_workspace_settings(expected_edit_version, command)
        except StateConflict:
            raise
        return self._view(stored)
