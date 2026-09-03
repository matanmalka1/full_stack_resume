from __future__ import annotations

from ...application.ai_configuration import AIModel, ReasoningEffort
from ...application.settings import ExecutionMode, UiDensity, UiTextSize
from .health import HttpSchema


class AIModelOptionResponse(HttpSchema):
    id: AIModel
    label: str
    input_per_million_usd: str
    cached_input_per_million_usd: str
    output_per_million_usd: str
    recommended: bool
    pricing_version: str
    pricing_source: str


class SettingsResponse(HttpSchema):
    edit_version: int
    auto_generate_when_review_not_required: bool
    ai_enabled: bool
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    available_ai_models: list[AIModelOptionResponse]
    ui_density: UiDensity
    ui_text_size: UiTextSize
    provider_configured: bool
    updated_at: str | None = None


class UpdateSettingsRequest(HttpSchema):
    auto_generate_when_review_not_required: bool
    ai_enabled_override: bool | None = None
    default_execution_mode: ExecutionMode
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    ui_density: UiDensity
    ui_text_size: UiTextSize
