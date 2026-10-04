"""Reading and updating the safe application settings the Web client may change."""

from __future__ import annotations

from ..ai_configuration import (
    AI_MODELS,
    DEFAULT_AI_MODEL,
    PRICING_SOURCE,
    PRICING_VERSION,
    normalize_ai_model,
    normalize_reasoning_effort,
)
from ..ports.settings import SettingsRepository
from ..ports.transactions import TransactionManager
from ..settings import AIModelOption, SettingsView, StoredSettings, UpdateSettings


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
                    cache_write_per_million_usd=(
                        None
                        if item.cache_write_per_million_usd is None
                        else format(item.cache_write_per_million_usd, "f")
                    ),
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
