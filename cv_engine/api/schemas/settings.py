from __future__ import annotations

from ...application.ai_configuration import AIModel, ReasoningEffort
from ...application.settings import UiDensity, UiTextSize, UiTheme
from ...domain.templates import TemplateName
from .health import HttpSchema


class AIModelOptionResponse(HttpSchema):
    id: AIModel
    label: str
    input_per_million_usd: str
    cached_input_per_million_usd: str
    cache_write_per_million_usd: str | None
    output_per_million_usd: str
    recommended: bool
    pricing_version: str
    pricing_source: str


class TemplateOptionResponse(HttpSchema):
    id: TemplateName
    label: str
    description: str
    columns: int


class SettingsResponse(HttpSchema):
    edit_version: int
    auto_generate_when_review_not_required: bool
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    available_ai_models: list[AIModelOptionResponse]
    ui_density: UiDensity
    ui_text_size: UiTextSize
    ui_theme: UiTheme
    default_template: TemplateName | None
    available_templates: list[TemplateOptionResponse]
    provider_configured: bool
    updated_at: str | None = None


class UpdateSettingsRequest(HttpSchema):
    auto_generate_when_review_not_required: bool
    default_ai_model: AIModel
    default_reasoning_effort: ReasoningEffort
    ui_density: UiDensity
    ui_text_size: UiTextSize
    ui_theme: UiTheme
    #: The template a new CV document starts with; null is the track's own.
    default_template: TemplateName | None
