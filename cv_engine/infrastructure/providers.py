"""The OpenAI adapter: strict Structured Outputs in, typed Proposals out.

`OpenAIProvider` implements `application.ports.AIProvider`, one method per task,
over one HTTP attempt per call. It knows the Responses API, the strict
JSON-Schema envelope, how to classify an attempt's outcome and how to sanitize a
response, and it holds the only mapping from a task name to its output model.
It cannot save state and never retries: it has no repository, no payload store
and no local path context, so what it returns is an `AIAttempt` - an
`AICallRecord` whatever the outcome, and a Proposal only on success. Logging each
attempt and deciding whether to try again belong to the application.

Nothing here reads a task-contract version or a prompt version. Both arrive as
`TaskContracts`, loaded from the Knowledge files that declare them, so the
adapter cannot disagree with the record the application writes.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar, cast

from pydantic import BaseModel, ValidationError

from ..application.ai_configuration import (
    PRICING_SOURCE,
    PRICING_VERSION,
    execution_cost,
    model_definition,
    normalize_ai_model,
    normalize_reasoning_effort,
)
from ..application.errors import KnowledgeRejected, ProviderRefused
from ..application.ports import (
    AIAttempt,
    AnalysisContext,
    AssessClaimSupportContext,
    DraftResumeContext,
    RegenerateClaimContext,
    RegenerateSectionContext,
    TaskContracts,
)
from ..application.transactions import assert_external_io_allowed
from ..domain.contracts.analysis_proposal import AnalysisProposal
from ..domain.contracts.base import StrictModel
from ..domain.contracts.providers import (
    AICallOutcome,
    AICallRecord,
    ClaimProposal,
    ClaimSupportProposal,
    DraftProposal,
    ProviderCost,
    ProviderPricing,
    ProviderUsage,
    SectionProposal,
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
    `DraftProposal`'s claims alone go from two required fields to four. The input
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


#: Billing refusals among 429 answers (OpenAI error codes). Retrying one does not
#: restore access, so it is `quota_exhausted` and never retried.
_QUOTA_ERROR_CODES = frozenset(
    {
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
        "insufficient_quota",
    }
)

#: A non-JSON body is kept as text up to this many characters.
_ERROR_BODY_TEXT_LIMIT = 2000

#: Credential-shaped text in a body that is not JSON, where a key cannot mark it.
_SECRET_TEXT = re.compile(r"(?i)(bearer\s+\S+|sk-[a-z0-9_-]{8,})")


def _sanitized_body(content_type: str | None, body: bytes) -> dict[str, Any]:
    """Any response body, as a sanitized JSON object.

    A JSON object is sanitized by key. Anything else - HTML from a proxy, plain
    text, a JSON scalar - is kept as truncated text with credential-shaped runs
    redacted, so every body fits the log and none carries a secret.
    """
    text = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        return sanitize_response(parsed)
    return {
        "content_type": content_type or "",
        "body_text": _SECRET_TEXT.sub("[redacted]", text[:_ERROR_BODY_TEXT_LIMIT]),
        "truncated": len(text) > _ERROR_BODY_TEXT_LIMIT,
    }


def _retry_after_seconds(value: str | None) -> float | None:
    """`Retry-After` as seconds from now: delta-seconds or an HTTP-date; else None."""
    if value is None:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            moment = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        seconds = (moment - datetime.now(UTC)).total_seconds()
    if seconds != seconds or seconds in (float("inf"), float("-inf")):
        return None
    return max(seconds, 0.0)


def _precise_now() -> str:
    """A call's own timestamps keep microseconds: they order attempts and bound latency."""
    return datetime.now(UTC).isoformat()


def _delivered_nowhere(error: urllib.error.URLError) -> bool:
    """True only when the failure provably happened before any connection existed.

    `urlopen` wraps every `OSError` raised while connecting *and while sending* in
    `URLError`, so the wrapper alone proves nothing. A failed name lookup and a
    refused connection are the two reasons that cannot occur once a connection is
    open; everything else - a timeout, a reset, a TLS or tunnel failure - may have
    happened after the request was on the wire.
    """
    return isinstance(error.reason, (socket.gaierror, ConnectionRefusedError))


@dataclass(frozen=True)
class _HttpAnswer:
    status: int
    content_type: str | None
    retry_after: str | None
    body: bytes


class _TransportFailure(Exception):
    def __init__(self, outcome: AICallOutcome, error_type: str, detail: str):
        super().__init__(detail)
        self.outcome: AICallOutcome = outcome
        self.error_type = error_type
        self.detail = detail


#: The one mapping from a contracted task name to the model its output must
#: satisfy. Derived from here by both the request schema and the parse, so a
#: task cannot be requested under one schema and validated against another.
TASK_OUTPUT_MODELS: dict[str, type[StrictModel]] = {
    "propose_analysis": AnalysisProposal,
    "draft_resume": DraftProposal,
    "assess_claim_support": ClaimSupportProposal,
    "regenerate_section": SectionProposal,
    "regenerate_claim": ClaimProposal,
}


class OpenAIProvider:
    """The five contracted tasks over the Responses API, one HTTP attempt per call.

    Strict Structured Outputs over the standard-library HTTP client, so the
    provider boundary adds no SDK dependency; the answer is still validated by
    the shared Pydantic output contract before it can enter core state.

    An Operation supplies the model and reasoning effort it froze at submission.
    The task-contract model remains a backend-only fallback for direct
    application calls; it is never accepted from an HTTP request.

    The API key is supplied by the caller - resolved through the config
    contract, not read from the environment here - and held only on this
    instance. It is never returned, logged, or written into a record: no record
    field can hold it, headers are never captured, and the sanitizer removes any
    header-shaped key that a provider echoes back.
    """

    name = "openai"

    def __init__(
        self,
        contracts: TaskContracts,
        *,
        default_model: str,
        api_key: str | None = None,
        timeout: int = 90,
    ):
        if not api_key:
            raise ProviderRefused("OPENAI_API_KEY is required when provider=openai")
        self._contracts = contracts
        self._default_model = default_model
        self.api_key = api_key
        self.timeout = timeout

    def _request_body(
        self,
        task: str,
        payload: dict[str, Any],
        output_model: type[StrictModel],
        model: str,
        reasoning_effort: str,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "reasoning": {"effort": reasoning_effort},
            "input": [
                {"role": "system", "content": self._contracts.prompt_text},
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

    def _post(self, body: dict[str, Any]) -> _HttpAnswer:
        """One HTTP request. An HTTP status is an answer; only transport failures raise."""
        assert_external_io_allowed("provider HTTP request")
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
                return _HttpAnswer(
                    status=response.status,
                    content_type=response.headers.get("Content-Type"),
                    retry_after=response.headers.get("Retry-After"),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            # Checked before `URLError`, which it subclasses: a status is an answer.
            try:
                payload = exc.read()
            except (OSError, http.client.HTTPException):
                payload = b""
            headers = exc.headers
            return _HttpAnswer(
                status=exc.code,
                content_type=None if headers is None else headers.get("Content-Type"),
                retry_after=None if headers is None else headers.get("Retry-After"),
                body=payload,
            )
        except urllib.error.URLError as exc:
            reason = exc.reason
            if _delivered_nowhere(exc):
                raise _TransportFailure(
                    "not_delivered",
                    type(reason).__name__,
                    "The AI provider could not be reached; nothing was sent.",
                ) from exc
            raise _TransportFailure(
                "outcome_unknown",
                type(reason).__name__ if isinstance(reason, BaseException) else "URLError",
                "The connection to the AI provider failed; it may have received the request.",
            ) from exc
        except (OSError, http.client.HTTPException) as exc:
            # Raised by `getresponse` or the body read: the request was sent in full.
            raise _TransportFailure(
                "outcome_unknown",
                type(exc).__name__,
                "The AI provider did not answer; it may have processed the request.",
            ) from exc

    def _run(
        self,
        task: str,
        context: StrictModel,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> AIAttempt[Any]:
        """One HTTP attempt for one task, whatever its outcome.

        Never raises for a classified outcome: a refusal, a schema violation, an
        HTTP error and a transport failure all come back in the `AIAttempt`'s
        record, so the application can log the attempt before it decides whether
        to try again. It never retries by itself.
        """
        assert_external_io_allowed("provider execution")
        contracts = self._contracts
        contract = contracts.get(task)
        output_model = TASK_OUTPUT_MODELS[task]
        # The contract file names the input and output models. Checked here
        # rather than trusted, because a name nobody enforces is a comment: a
        # contract that says `AnalysisProposal` while the code sends
        # something else would persist a false `output_schema_version` into an
        # immutable record, and every test would still pass.
        declared = {"input": contract.input, "output": contract.output}
        actual = {"input": type(context).__name__, "output": output_model.__name__}
        if declared != actual:
            raise KnowledgeRejected(
                f"AI task contract {task} declares {declared} but the engine sends {actual}"
            )
        selected_model = normalize_ai_model(model or contract.model or self._default_model)
        selected_effort = normalize_reasoning_effort(reasoning_effort)
        payload = context.model_dump(mode="json")
        body = self._request_body(task, payload, output_model, selected_model, selected_effort)
        started_at = _precise_now()
        started = time.monotonic()

        def record(outcome: AICallOutcome, detail: str, **fields: Any) -> AICallRecord:
            sanitized = fields.pop("sanitized_response", None)
            return AICallRecord(
                task=task,
                provider=self.name,
                model=selected_model,
                reasoning_effort=selected_effort,
                task_contract_version=contract.version,
                input_schema_version=contract.input_schema_version,
                input_schema_hash=schema_hash(model_schema(type(context))),
                output_schema_version=contract.output_schema_version,
                output_schema_hash=schema_hash(body["text"]["format"]["schema"]),
                prompt_version=contracts.prompt_version,
                prompt_hash=contracts.prompt_hash,
                input_hash=sha256_text(canonical_json(payload)),
                outcome=outcome,
                sanitized_response=sanitized,
                sanitized_response_hash=(
                    None if sanitized is None else sha256_text(canonical_json(sanitized))
                ),
                latency_ms=int((time.monotonic() - started) * 1000),
                started_at=started_at,
                finished_at=_precise_now(),
                detail=detail,
                **fields,
            )

        try:
            answer = self._post(body)
        except _TransportFailure as failure:
            return AIAttempt(record(failure.outcome, failure.detail, error_type=failure.error_type))

        if answer.status >= 300:
            return AIAttempt(self._http_failure(answer, record))

        sanitized = _sanitized_body(answer.content_type, answer.body)
        try:
            envelope = json.loads(answer.body.decode("utf-8"))
        except ValueError:
            envelope = None
        if not isinstance(envelope, dict):
            return AIAttempt(
                record(
                    "schema_violation",
                    "The AI provider response is not a JSON object.",
                    http_status=answer.status,
                    sanitized_response=sanitized,
                )
            )
        usage, pricing, cost = _usage(envelope, selected_model)
        answered: dict[str, Any] = {
            "http_status": answer.status,
            "response_id": envelope.get("id"),
            "sanitized_response": sanitized,
            "usage": usage,
            "pricing": pricing,
            "cost": cost,
        }
        texts = [
            content["text"]
            for item in envelope.get("output", [])
            if isinstance(item, dict)
            for content in item.get("content", [])
            if isinstance(content, dict) and content.get("type") == "output_text"
        ]
        if not texts:
            return AIAttempt(record("refused", "The AI provider refused the request.", **answered))
        try:
            parsed = output_model.model_validate_json("".join(texts))
        except (ValidationError, ValueError):
            return AIAttempt(
                record(
                    "schema_violation",
                    f"The AI provider output does not satisfy the {task} schema.",
                    **answered,
                )
            )
        return AIAttempt(
            record(
                "succeeded",
                "",
                output_hash=sha256_text(canonical_json(parsed.model_dump(mode="json"))),
                **answered,
            ),
            parsed,
        )

    def _http_failure(
        self, answer: _HttpAnswer, record: Callable[..., AICallRecord]
    ) -> AICallRecord:
        sanitized = _sanitized_body(answer.content_type, answer.body)
        found = sanitized.get("error")
        error: dict[str, Any] = found if isinstance(found, dict) else {}
        error_type = error.get("type") if isinstance(error.get("type"), str) else None
        error_code = error.get("code") if isinstance(error.get("code"), str) else None
        fields: dict[str, Any] = {
            "http_status": answer.status,
            "error_type": error_type,
            "error_code": error_code,
            "retry_after_seconds": _retry_after_seconds(answer.retry_after),
            "sanitized_response": sanitized,
        }
        if answer.status == 429:
            if error_code in _QUOTA_ERROR_CODES or error_type == "insufficient_quota":
                return record(
                    "quota_exhausted",
                    "The AI provider account has no remaining quota or credit.",
                    **fields,
                )
            return record("rate_limited", "The AI provider rate limited the request.", **fields)
        return record("http_error", f"The AI provider returned HTTP {answer.status}.", **fields)

    def propose_analysis(
        self,
        context: AnalysisContext,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> AIAttempt[AnalysisProposal]:
        return cast(
            AIAttempt[AnalysisProposal],
            self._run("propose_analysis", context, model=model, reasoning_effort=reasoning_effort),
        )

    def draft_resume(
        self,
        context: DraftResumeContext,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> AIAttempt[DraftProposal]:
        return cast(
            AIAttempt[DraftProposal],
            self._run("draft_resume", context, model=model, reasoning_effort=reasoning_effort),
        )

    def assess_claim_support(
        self,
        context: AssessClaimSupportContext,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> AIAttempt[ClaimSupportProposal]:
        return cast(
            AIAttempt[ClaimSupportProposal],
            self._run(
                "assess_claim_support", context, model=model, reasoning_effort=reasoning_effort
            ),
        )

    def regenerate_section(
        self,
        context: RegenerateSectionContext,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> AIAttempt[SectionProposal]:
        return cast(
            AIAttempt[SectionProposal],
            self._run(
                "regenerate_section", context, model=model, reasoning_effort=reasoning_effort
            ),
        )

    def regenerate_claim(
        self,
        context: RegenerateClaimContext,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> AIAttempt[ClaimProposal]:
        return cast(
            AIAttempt[ClaimProposal],
            self._run("regenerate_claim", context, model=model, reasoning_effort=reasoning_effort),
        )


def _usage(envelope: dict[str, Any], model: str):
    """Usage, its price snapshot and cost - each None when not reported in full.

    A usage the provider did not report, or reported inconsistently, is unknown;
    so is a cost that needs a count the provider left out. None is never read
    as zero.
    """
    raw = envelope.get("usage")
    if not isinstance(raw, dict):
        return None, None, None
    details = raw.get("input_tokens_details")
    if not isinstance(details, dict):
        return None, None, None
    try:
        usage = ProviderUsage(
            input_tokens=raw["input_tokens"],
            cached_input_tokens=details["cached_tokens"],
            cache_write_tokens=details.get("cache_write_tokens"),
            output_tokens=raw["output_tokens"],
            total_tokens=raw["total_tokens"],
        )
    except (KeyError, TypeError, ValidationError):
        return None, None, None
    definition = model_definition(model)
    pricing = ProviderPricing(
        version=PRICING_VERSION,
        source=PRICING_SOURCE,
        input_per_million_usd=format(definition.input_per_million_usd, "f"),
        cached_input_per_million_usd=format(definition.cached_input_per_million_usd, "f"),
        cache_write_per_million_usd=format(
            definition.cache_write_per_million_usd or Decimal(0), "f"
        ),
        output_per_million_usd=format(definition.output_per_million_usd, "f"),
        long_context_threshold_tokens=definition.long_context_threshold_tokens,
        long_context_input_multiplier=format(definition.long_context_input_multiplier, "f"),
        long_context_output_multiplier=format(definition.long_context_output_multiplier, "f"),
    )
    cost = execution_cost(
        model,
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.cached_input_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        output_tokens=usage.output_tokens,
    )
    return usage, pricing, None if cost is None else ProviderCost(**cost)
