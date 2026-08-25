"""The OpenAI adapter: strict Structured Outputs in, typed Proposals out.

Two layers, deliberately separate.

`StructuredOutputClient` is *transport*. It knows the Responses API, the strict
JSON-Schema envelope, HTTP status classification, and how to sanitize a raw
response. It knows nothing about job analyses, selection plans, or drafts. It
was called `AIProvider` until Stage G, which is the name the application layer
needs for its own contract - a protocol describing five product tasks, not one
describing an HTTP call.

`OpenAIProvider` is the *contract*. It implements `application.ports.AIProvider`,
one method per task, and it holds the only mapping from a task name to its
output model. It cannot save state: it has no repository, no payload store, and
no Workspace, so what it returns stays a Proposal until the application commits
it.

Nothing here reads a task-contract version or a prompt version. Both arrive as
`TaskContracts`, loaded from the Knowledge files that declare them, so the
adapter cannot disagree with the record the application writes.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Protocol, TypeVar, cast

from pydantic import BaseModel, ValidationError

from ..application.errors import (
    KnowledgeRejected,
    ProviderRateLimited,
    ProviderRefused,
    ProviderSchemaViolation,
    ProviderTimeout,
    ProviderUnavailable,
)
from ..application.ports import (
    AIProposal,
    DraftResumeContext,
    JobAnalysisContext,
    RegenerateClaimContext,
    RegenerateSectionContext,
    SelectionPlanContext,
    TaskContracts,
)
from ..domain.models import (
    ClaimProposal,
    DraftProposal,
    JobClassificationProposal,
    ProviderContext,
    ProviderTaskResult,
    ProviderUsage,
    SectionProposal,
    SelectionProposal,
    StrictModel,
)
from ..util import canonical_json, sha256_text

OutputT = TypeVar("OutputT", bound=BaseModel)

#: Envelope keys that could carry a credential or hidden reasoning. Removed
#: before the raw response is preserved, and matched on the key rather than on
#: the value, so a secret cannot survive by not looking like one.
_REDACTED_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "reasoning",
        "reasoning_content",
        "encrypted_content",
        "thinking",
    }
)

#: Response output items that exist only to carry hidden chain-of-thought.
#: Dropped whole: keeping the item and redacting its contents would still
#: preserve its token counts and ordering as a shadow of the reasoning.
_REDACTED_ITEM_TYPES = frozenset({"reasoning"})


class ProviderError(ProviderUnavailable):
    """Backwards-compatible alias for an unclassified provider transport failure.

    Kept as a name because `ProviderUnavailable` is the honest default for a
    call that did not produce a usable answer and did not identify itself as
    anything more specific.
    """


class StructuredOutputClient(Protocol):
    """Transport: one strict Structured Outputs call, and what it cost.

    Deliberately stringly-typed in `task`, because at this level a task *is*
    just the schema name that goes into the request. The typed contract is one
    layer up, where the five tasks have five different inputs.
    """

    name: str
    model: str

    def run(
        self,
        task: str,
        payload: dict[str, Any],
        output_model: type[OutputT],
        *,
        contracts: TaskContracts,
        input_model: type[BaseModel] | None = None,
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


def schema_hash(schema: dict[str, Any] | None) -> str:
    """The exact identity of one JSON Schema document.

    Derived rather than declared, so it cannot fall out of date. The declared
    `*_schema_version` in the contract file is the label a human reads; this is
    what proves which shape actually governed the boundary.

    It must be given **the schema that was really used**, which is not the same
    document on both sides. The output schema is the strict one in the request:
    `_strict_schema` rewrites `required` and closes every object, so hashing
    `model_json_schema()` would record a shape the provider was never sent -
    `SelectionProposal` alone goes from one required field to three. The input
    schema is the model's own, because no input schema is transmitted at all;
    what crosses is a payload serialized from that model.
    """
    if schema is None:
        return ""
    return sha256_text(canonical_json(schema))


def model_schema(model: type[BaseModel] | None) -> dict[str, Any] | None:
    return None if model is None else model.model_json_schema()


def sanitize_response(envelope: Any) -> Any:
    """Strip credentials and hidden reasoning from a provider envelope.

    Applied before the response is hashed and before it is preserved, so the
    stored artifact and its recorded hash describe the same sanitized bytes.
    There is no path by which the unsanitized envelope reaches a payload.
    """
    if isinstance(envelope, dict):
        cleaned: dict[str, Any] = {}
        for key, value in envelope.items():
            normalized = str(key).strip().casefold().replace("-", "_")
            if normalized in _REDACTED_KEYS:
                continue
            cleaned[key] = sanitize_response(value)
        return cleaned
    if isinstance(envelope, list):
        return [
            sanitize_response(item)
            for item in envelope
            if not (isinstance(item, dict) and item.get("type") in _REDACTED_ITEM_TYPES)
        ]
    return envelope


class OpenAIResponsesProvider:
    """Responses API adapter using strict Structured Outputs.

    It intentionally uses the standard library HTTP client so the provider
    boundary does not add an SDK dependency. The response is still validated by
    the shared Pydantic output contract before it can enter core state.

    The API key is supplied by the caller - resolved through the config
    contract, not read from the environment here - and held only on this
    instance. It is never returned, logged, or written into provenance:
    `ProviderContext` has no field it could occupy, and the sanitizer removes
    any header-shaped key that a provider echoes back.
    """

    name = "openai"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        timeout: int = 90,
    ):
        self.model = model
        self.api_key = api_key
        if not self.api_key:
            raise ProviderRefused("OPENAI_API_KEY is required when provider=openai")
        self.timeout = timeout

    def _request_body(
        self,
        task: str,
        payload: dict[str, Any],
        output_model: type[OutputT],
        contracts: TaskContracts,
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": [
                {"role": "system", "content": contracts.prompt_text},
                {"role": "user", "content": canonical_json({"task": task, "input": payload})},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": task.replace("-", "_"),
                    "strict": True,
                    "schema": _strict_schema(output_model.model_json_schema()),
                }
            },
        }

    def _post(self, body: dict[str, Any]) -> str:
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=canonical_json(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code == 429:
                raise ProviderRateLimited(f"provider rate limited: {detail}") from exc
            if exc.code >= 500:
                raise ProviderUnavailable(f"provider returned {exc.code}: {detail}") from exc
            raise ProviderRefused(f"provider returned {exc.code}: {detail}") from exc
        except TimeoutError as exc:
            raise ProviderTimeout("provider request timed out") from exc
        except OSError as exc:
            # `socket.timeout` is `TimeoutError` on 3.10+, so the ordering above
            # already separates the two; everything else that never reached the
            # provider is an availability failure, and both are retried once.
            raise ProviderUnavailable(f"provider request failed: {exc}") from exc

    def run(
        self,
        task: str,
        payload: dict[str, Any],
        output_model: type[OutputT],
        *,
        contracts: TaskContracts,
        input_model: type[BaseModel] | None = None,
    ) -> tuple[OutputT, ProviderTaskResult]:
        contract = contracts.get(task)
        body = self._request_body(task, payload, output_model, contracts)
        started = time.monotonic()
        raw = self._post(body)
        latency_ms = int((time.monotonic() - started) * 1000)

        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderSchemaViolation("provider response is not JSON") from exc
        sanitized = canonical_json(sanitize_response(envelope))
        usage = envelope.get("usage") or {}

        def provenance_for(output: dict[str, Any]) -> ProviderTaskResult:
            """One provenance shape, whether the answer was used or refused.

            Built here rather than only on the success path so a refusal can
            carry it. A refused answer with no record of which model produced it
            is evidence of very little.
            """
            return ProviderTaskResult(
                task=task,
                output=output,
                context=ProviderContext(
                    provider=self.name,
                    model=self.model,
                    task_contract_version=contract.version,
                    prompt_version=contracts.prompt_version,
                    prompt_hash=contracts.prompt_hash,
                    system_version=contracts.version,
                    input_schema_version=contract.input_schema_version,
                    input_schema_hash=schema_hash(model_schema(input_model)),
                    output_schema_version=contract.output_schema_version,
                    output_schema_hash=schema_hash(body["text"]["format"]["schema"]),
                    response_id=envelope.get("id"),
                    usage=ProviderUsage(
                        input_tokens=int(usage.get("input_tokens") or 0),
                        output_tokens=int(usage.get("output_tokens") or 0),
                        total_tokens=int(usage.get("total_tokens") or 0),
                    ),
                    latency_ms=latency_ms,
                ),
                input_hash=sha256_text(canonical_json(payload)),
                output_hash=sha256_text(canonical_json(output)) if output else "",
                raw_output_hash=sha256_text(sanitized),
                sanitized_response=sanitized,
            )

        texts = [
            content["text"]
            for item in envelope.get("output", [])
            if isinstance(item, dict)
            for content in item.get("content", [])
            if isinstance(content, dict) and content.get("type") == "output_text"
        ]
        if not texts:
            refusals = [
                content.get("refusal")
                for item in envelope.get("output", [])
                if isinstance(item, dict)
                for content in item.get("content", [])
                if isinstance(content, dict) and content.get("type") == "refusal"
            ]
            raise ProviderRefused(
                f"provider returned no structured text; refusals={refusals}",
                provenance=provenance_for({}),
            )
        try:
            parsed = output_model.model_validate_json("".join(texts))
        except (ValidationError, ValueError) as exc:
            # The sanitized bytes travel with the refusal. They are the only
            # copy of what the provider actually said, and §6 invariant 15 keeps
            # a refused output as inactive immutable evidence rather than
            # discarding it at the point it is rejected.
            raise ProviderSchemaViolation(
                f"provider output does not satisfy the {task} schema",
                provenance=provenance_for({}),
            ) from exc

        provenance = provenance_for(parsed.model_dump(mode="json"))
        return parsed, provenance


#: The one mapping from a contracted task name to the model its output must
#: satisfy. Derived from here by both the request schema and the parse, so a
#: task cannot be requested under one schema and validated against another.
TASK_OUTPUT_MODELS: dict[str, type[StrictModel]] = {
    "propose_job_analysis": JobClassificationProposal,
    "propose_selection_plan": SelectionProposal,
    "draft_resume": DraftProposal,
    "regenerate_section": SectionProposal,
    "regenerate_claim": ClaimProposal,
}


class OpenAIProvider:
    """The five contracted tasks, behind the application's `AIProvider` port.

    The per-task model override comes from the task contract rather than from a
    caller: architecture §11 makes default model and per-task overrides backend
    configuration, and a caller that could choose a model per call would make
    the stored `model` a client's opinion rather than the installation's.
    """

    def __init__(
        self,
        contracts: TaskContracts,
        *,
        default_model: str,
        api_key: str | None = None,
        client_factory: Any = None,
    ):
        self._contracts = contracts
        self._default_model = default_model
        self._client_factory = client_factory or (
            lambda model: OpenAIResponsesProvider(model=model, api_key=api_key)
        )

    def _run(self, task: str, context: StrictModel):
        contract = self._contracts.get(task)
        output_model = TASK_OUTPUT_MODELS[task]
        # The contract file names the input and output models. Checked here
        # rather than trusted, because a name nobody enforces is a comment: a
        # contract that says `JobClassificationProposal` while the code sends
        # something else would persist a false `output_schema_version` into an
        # immutable record, and every test would still pass.
        declared = {"input": contract.input, "output": contract.output}
        actual = {"input": type(context).__name__, "output": output_model.__name__}
        if declared != actual:
            raise KnowledgeRejected(
                f"AI task contract {task} declares {declared} but the engine sends {actual}"
            )
        client = self._client_factory(contract.model or self._default_model)
        return client.run(
            task,
            context.model_dump(mode="json"),
            output_model,
            contracts=self._contracts,
            input_model=type(context),
        )

    def propose_job_analysis(
        self, context: JobAnalysisContext
    ) -> AIProposal[JobClassificationProposal]:
        proposal, provenance = self._run("propose_job_analysis", context)
        return AIProposal(proposal=cast(JobClassificationProposal, proposal), provenance=provenance)

    def propose_selection_plan(
        self, context: SelectionPlanContext
    ) -> AIProposal[SelectionProposal]:
        proposal, provenance = self._run("propose_selection_plan", context)
        return AIProposal(proposal=cast(SelectionProposal, proposal), provenance=provenance)

    def draft_resume(self, context: DraftResumeContext) -> AIProposal[DraftProposal]:
        proposal, provenance = self._run("draft_resume", context)
        return AIProposal(proposal=cast(DraftProposal, proposal), provenance=provenance)

    def regenerate_section(self, context: RegenerateSectionContext) -> AIProposal[SectionProposal]:
        proposal, provenance = self._run("regenerate_section", context)
        return AIProposal(proposal=cast(SectionProposal, proposal), provenance=provenance)

    def regenerate_claim(self, context: RegenerateClaimContext) -> AIProposal[ClaimProposal]:
        proposal, provenance = self._run("regenerate_claim", context)
        return AIProposal(proposal=cast(ClaimProposal, proposal), provenance=provenance)
