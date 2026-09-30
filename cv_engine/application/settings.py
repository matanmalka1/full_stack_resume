"""Safe, mutable application settings exposed to the local Web client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

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

if TYPE_CHECKING:
    from .ports.transactions import ReadTransaction, TransactionManager, WriteTransaction

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


class SettingsRepository(Protocol):
    def settings(self, tx: ReadTransaction) -> StoredSettings: ...

    def update_settings(
        self, tx: WriteTransaction, expected_edit_version: int, settings: UpdateSettings
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
        transactions: TransactionManager,
        repository: SettingsRepository,
        *,
        provider_configured: bool,
        runtime_default_model: str = DEFAULT_AI_MODEL,
    ):
        self.transactions = transactions
        self.repo = repository
        self.provider_configured = provider_configured
        self.runtime_default_model = normalize_ai_model(runtime_default_model)

    def _view(self, stored: StoredSettings) -> SettingsView:
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
            provider_configured=self.provider_configured,
        )

    def read(self) -> SettingsView:
        with self.transactions.read() as tx:
            stored = self.repo.settings(tx)
        return self._view(stored)

    def update(self, expected_edit_version: int, command: UpdateSettings) -> SettingsView:
        normalize_ai_model(command.default_ai_model)
        normalize_reasoning_effort(command.default_reasoning_effort)
        with self.transactions.write() as tx:
            stored = self.repo.update_settings(tx, expected_edit_version, command)
        return self._view(stored)
