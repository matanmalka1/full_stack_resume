"""Safe, mutable application settings exposed to the local Web client."""

from __future__ import annotations

from typing import Literal, Protocol

from .ai_configuration import (
    AI_MODELS,
    DEFAULT_AI_MODEL,
    DEFAULT_REASONING_EFFORT,
    PRICING_SOURCE,
    PRICING_VERSION,
    AIModel,
    ReasoningEffort,
    normalize_ai_model,
    normalize_reasoning_effort,
)
from .commands import BoundaryDTO
from .errors import PreconditionFailed

ExecutionMode = Literal["deterministic", "ai"]
UiDensity = Literal["comfortable", "compact"]
UiTextSize = Literal["normal", "large"]


class StoredSettings(BoundaryDTO):
    edit_version: int = 0
    auto_generate_when_review_not_required: bool = False
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode = "deterministic"
    default_ai_model: AIModel | None = None
    default_reasoning_effort: ReasoningEffort = DEFAULT_REASONING_EFFORT
    ui_density: UiDensity = "comfortable"
    ui_text_size: UiTextSize = "normal"
    updated_at: str | None = None


class SettingsView(BoundaryDTO):
    edit_version: int
    auto_generate_when_review_not_required: bool
    ai_enabled: bool
    ai_enabled_override: bool | None
    default_execution_mode: ExecutionMode
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    available_ai_models: list[AIModelOption]
    ui_density: UiDensity
    ui_text_size: UiTextSize
    provider_configured: bool
    updated_at: str | None = None


class UpdateSettings(BoundaryDTO):
    auto_generate_when_review_not_required: bool
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    ui_density: UiDensity
    ui_text_size: UiTextSize


class SettingsRepository(Protocol):
    def app_settings(self) -> StoredSettings: ...

    def update_app_settings(
        self, expected_edit_version: int, settings: UpdateSettings
    ) -> StoredSettings: ...


class AIModelOption(BoundaryDTO):
    id: AIModel
    label: str
    input_per_million_usd: str
    cached_input_per_million_usd: str
    output_per_million_usd: str
    recommended: bool
    pricing_version: str
    pricing_source: str


class SettingsService:
    def __init__(
        self,
        repository: SettingsRepository,
        *,
        provider_configured: bool,
        runtime_default_model: str = DEFAULT_AI_MODEL,
    ):
        self.repo = repository
        self.provider_configured = provider_configured
        self.runtime_default_model = normalize_ai_model(runtime_default_model)

    def _view(self, stored: StoredSettings) -> SettingsView:
        enabled = self.provider_configured and stored.ai_enabled_override is not False
        selected_model = normalize_ai_model(stored.default_ai_model or self.runtime_default_model)
        return SettingsView(
            **stored.model_dump(mode="python", exclude={"default_ai_model"}),
            default_ai_model=selected_model,
            available_ai_models=[
                AIModelOption(
                    id=item.id,
                    label=item.label,
                    input_per_million_usd=format(item.input_per_million_usd, "f"),
                    cached_input_per_million_usd=format(item.cached_input_per_million_usd, "f"),
                    output_per_million_usd=format(item.output_per_million_usd, "f"),
                    recommended=item.recommended,
                    pricing_version=PRICING_VERSION,
                    pricing_source=PRICING_SOURCE,
                )
                for item in AI_MODELS
            ],
            ai_enabled=enabled,
            provider_configured=self.provider_configured,
        )

    def read(self) -> SettingsView:
        return self._view(self.repo.app_settings())

    def update(self, expected_edit_version: int, command: UpdateSettings) -> SettingsView:
        normalize_ai_model(command.default_ai_model)
        normalize_reasoning_effort(command.default_reasoning_effort)
        enabled = self.provider_configured and command.ai_enabled_override is not False
        if command.default_execution_mode == "ai" and not (self.provider_configured and enabled):
            raise PreconditionFailed(
                "AI cannot be the default execution mode until it is enabled and configured"
            )
        stored = self.repo.update_app_settings(expected_edit_version, command)
        return self._view(stored)
