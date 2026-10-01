"""Contracts for the safe, mutable application settings exposed to the Web client."""

from __future__ import annotations

from typing import Literal

from .ai_configuration import DEFAULT_REASONING_EFFORT, AIModel, ReasoningEffort
from .commands import BoundaryDTO

UiDensity = Literal["comfortable", "compact"]
UiTextSize = Literal["normal", "large"]
UiTheme = Literal["system", "light", "dark"]


class StoredSettings(BoundaryDTO):
    edit_version: int = 0
    auto_generate_when_review_not_required: bool = False
    default_ai_model: AIModel | None = None
    default_reasoning_effort: ReasoningEffort = DEFAULT_REASONING_EFFORT
    ui_density: UiDensity = "comfortable"
    ui_text_size: UiTextSize = "normal"
    ui_theme: UiTheme = "system"
    updated_at: str | None = None


class SettingsView(BoundaryDTO):
    edit_version: int
    auto_generate_when_review_not_required: bool
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    available_ai_models: list[AIModelOption]
    ui_density: UiDensity
    ui_text_size: UiTextSize
    ui_theme: UiTheme
    provider_configured: bool
    updated_at: str | None = None


class UpdateSettings(BoundaryDTO):
    auto_generate_when_review_not_required: bool
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    ui_density: UiDensity
    ui_text_size: UiTextSize
    ui_theme: UiTheme


class AIModelOption(BoundaryDTO):
    id: AIModel
    label: str
    input_per_million_usd: str
    cached_input_per_million_usd: str
    cache_write_per_million_usd: str | None
    output_per_million_usd: str
    recommended: bool
    pricing_version: str
    pricing_source: str
