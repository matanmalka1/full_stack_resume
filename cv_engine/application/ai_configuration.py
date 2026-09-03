"""Allowed AI execution choices and auditable OpenAI pricing.

The Web client receives this catalog from the application instead of carrying its own
model or price list. Prices are a versioned snapshot: provider artifacts retain the
rates used for their calculation, so a later catalog update cannot rewrite historical
costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, TypedDict, cast

AIModel = Literal["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"]
ReasoningEffort = Literal["low", "medium", "high"]

DEFAULT_AI_MODEL: AIModel = "gpt-5.6-terra"
DEFAULT_REASONING_EFFORT: ReasoningEffort = "medium"
PRICING_VERSION = "openai-2026-09-03"
PRICING_SOURCE = "https://developers.openai.com/api/docs/models/compare"


@dataclass(frozen=True)
class AIModelDefinition:
    id: AIModel
    label: str
    input_per_million_usd: Decimal
    cached_input_per_million_usd: Decimal
    output_per_million_usd: Decimal
    long_context_threshold_tokens: int = 272_000
    long_context_input_multiplier: Decimal = Decimal("2")
    long_context_output_multiplier: Decimal = Decimal("1.5")
    recommended: bool = False


AI_MODELS: tuple[AIModelDefinition, ...] = (
    AIModelDefinition(
        "gpt-5.6-luna",
        "GPT-5.6 Luna",
        Decimal("0.20"),
        Decimal("0.02"),
        Decimal("1.20"),
    ),
    AIModelDefinition(
        "gpt-5.6-terra",
        "GPT-5.6 Terra",
        Decimal("2.00"),
        Decimal("0.20"),
        Decimal("12.00"),
        recommended=True,
    ),
    AIModelDefinition(
        "gpt-5.6-sol",
        "GPT-5.6 Sol",
        Decimal("4.00"),
        Decimal("0.40"),
        Decimal("20.00"),
    ),
)
AI_MODEL_IDS: tuple[AIModel, ...] = tuple(item.id for item in AI_MODELS)
REASONING_EFFORTS: tuple[ReasoningEffort, ...] = ("low", "medium", "high")
_MODELS_BY_ID = {item.id: item for item in AI_MODELS}


class ExecutionCost(TypedDict):
    input_usd: str
    output_usd: str
    total_usd: str


def normalize_ai_model(value: str | None) -> AIModel:
    """Resolve the supported legacy alias and reject arbitrary provider slugs."""
    normalized = "gpt-5.6-sol" if value == "gpt-5.6" else value
    if normalized not in _MODELS_BY_ID:
        raise ValueError(f"unsupported AI model: {value}")
    return cast(AIModel, normalized)


def normalize_reasoning_effort(value: str | None) -> ReasoningEffort:
    normalized = value or DEFAULT_REASONING_EFFORT
    if normalized not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {value}")
    return cast(ReasoningEffort, normalized)


def model_definition(model: str) -> AIModelDefinition:
    return _MODELS_BY_ID[normalize_ai_model(model)]


def usd(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), "f")


def execution_cost(
    model: str,
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> ExecutionCost:
    definition = model_definition(model)
    cached = min(max(cached_input_tokens, 0), max(input_tokens, 0))
    uncached = max(input_tokens, 0) - cached
    divisor = Decimal(1_000_000)
    long_context = input_tokens > definition.long_context_threshold_tokens
    input_multiplier = definition.long_context_input_multiplier if long_context else Decimal(1)
    output_multiplier = definition.long_context_output_multiplier if long_context else Decimal(1)
    input_cost = (
        (
            Decimal(uncached) * definition.input_per_million_usd
            + Decimal(cached) * definition.cached_input_per_million_usd
        )
        * input_multiplier
        / divisor
    )
    output_cost = (
        Decimal(max(output_tokens, 0))
        * definition.output_per_million_usd
        * output_multiplier
        / divisor
    )
    return {
        "input_usd": usd(input_cost),
        "output_usd": usd(output_cost),
        "total_usd": usd(input_cost + output_cost),
    }
