from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from ..application.errors import InfrastructureFailure
from ..domain.models import JobClassificationProposal, ProviderContext, ProviderTaskResult
from ..util import canonical_json, sha256_text

OutputT = TypeVar("OutputT", bound=BaseModel)


class ProviderError(InfrastructureFailure):
    pass


class AIProvider(Protocol):
    name: str
    model: str

    def run(
        self, task: str, payload: dict[str, Any], output_model: type[OutputT]
    ) -> tuple[OutputT, ProviderTaskResult]: ...


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                node["additionalProperties"] = False
                properties = node.get("properties", {})
                node["required"] = list(properties)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    result = json.loads(json.dumps(schema))
    visit(result)
    return result


class OpenAIResponsesProvider:
    """Responses API adapter using strict Structured Outputs.

    It intentionally uses the standard library HTTP client so the provider boundary
    does not add an SDK dependency. The response is still validated by the shared
    Pydantic output contract before it can enter core state.
    """

    name = "openai"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        prompt_path: Path | None = None,
        timeout: int = 90,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is required when provider=openai")
        self.prompt_path = prompt_path
        self.timeout = timeout

    def run(
        self, task: str, payload: dict[str, Any], output_model: type[OutputT]
    ) -> tuple[OutputT, ProviderTaskResult]:
        system = (
            self.prompt_path.read_text(encoding="utf-8")
            if self.prompt_path
            else "Use only supplied canonical facts. Return the exact requested schema."
        )
        schema = _strict_schema(output_model.model_json_schema())
        request_body = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": canonical_json({"task": task, "input": payload})},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": task.replace("-", "_"),
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=canonical_json(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"OpenAI Responses API returned HTTP {exc.code}: {body[:1000]}"
            ) from exc
        except OSError as exc:
            raise ProviderError(f"OpenAI Responses API request failed: {exc}") from exc
        try:
            envelope = json.loads(raw)
            texts = [
                content["text"]
                for item in envelope.get("output", [])
                for content in item.get("content", [])
                if content.get("type") == "output_text"
            ]
            if not texts:
                refusals = [
                    content.get("refusal")
                    for item in envelope.get("output", [])
                    for content in item.get("content", [])
                    if content.get("type") == "refusal"
                ]
                raise ProviderError(f"provider returned no structured text; refusals={refusals}")
            parsed = output_model.model_validate_json("".join(texts))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise ProviderError(f"invalid provider structured output: {exc}") from exc
        provenance = ProviderTaskResult(
            task=task,
            output=parsed.model_dump(mode="json"),
            context=ProviderContext(
                provider=self.name,
                model=self.model,
                task_contract_version="1.0.0",
                prompt_version="system-v1",
            ),
            raw_output_hash=sha256_text(raw),
        )
        return parsed, provenance


class OpenAIClassificationProvider:
    """The one v1 AI task, behind the application's provider port."""

    def __init__(self, prompt_path: Path):
        self.prompt_path = Path(prompt_path)

    def classify_job(self, payload: dict[str, Any], *, model: str) -> JobClassificationProposal:
        adapter = OpenAIResponsesProvider(model=model, prompt_path=self.prompt_path)
        proposal, _raw = adapter.run("classify_job", payload, JobClassificationProposal)
        return proposal
