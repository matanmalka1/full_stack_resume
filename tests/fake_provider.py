"""A fake OpenAI transport, and nothing above it.

The seam is `urllib.request.urlopen`. Everything between the application port
and that call - the strict schema envelope, status classification, refusal
detection, sanitization, hashing, provenance, the task-to-model mapping - is
production code in these tests. A fake that reimplemented any of it would prove
that the fake works.

Scripts are per task. A script entry is either a Proposal model (answered
normally), an `HTTPStatus` (answered with that status), a `Timeout` (the request
never returns), or a raw dict (used as the response envelope verbatim, which is
how a schema-violating or refusing answer is expressed).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from cv_engine.infrastructure.providers import OpenAIProvider, OpenAIResponsesProvider


@dataclass(frozen=True)
class HTTPStatus:
    """Answer this call with an HTTP status instead of a body."""

    code: int
    body: str = '{"error": {"message": "scripted"}}'


@dataclass(frozen=True)
class Timeout:
    """Answer this call by never answering."""


@dataclass
class Call:
    task: str
    payload: dict[str, Any]
    body: dict[str, Any]


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        """`HTTPError` wraps its `fp` in a temp-file closer that calls this."""


def envelope(payload: Any, **extra: Any) -> dict[str, Any]:
    """A Responses API envelope carrying one structured output text."""
    text = payload if isinstance(payload, str) else payload.model_dump_json()
    return {
        "id": "resp_fake_1",
        "model": "gpt-test",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
        "usage": {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33},
        **extra,
    }


def refusal_envelope(reason: str = "I can't help with that.") -> dict[str, Any]:
    return {
        "id": "resp_fake_refusal",
        "model": "gpt-test",
        "output": [{"type": "message", "content": [{"type": "refusal", "refusal": reason}]}],
        "usage": {"input_tokens": 5, "output_tokens": 0, "total_tokens": 5},
    }


@dataclass
class FakeOpenAI:
    """One scripted transport, shared by every task in a test."""

    scripts: dict[str, list[Any]] = field(default_factory=lambda: defaultdict(list))
    calls: list[Call] = field(default_factory=list)

    def script(self, task: str, *answers: Any) -> FakeOpenAI:
        self.scripts.setdefault(task, []).extend(answers)
        return self

    def _next(self, task: str) -> Any:
        queue = self.scripts.get(task)
        if not queue:
            raise AssertionError(f"no scripted provider answer for task {task!r}")
        # The last answer repeats, so a test that only cares about the first
        # attempt does not have to script a retry it is not asserting on.
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def urlopen(self, request, timeout):  # noqa: ARG002 - matches urlopen's signature
        body = json.loads(request.data)
        task = body["text"]["format"]["name"]
        payload = json.loads(body["input"][1]["content"])["input"]
        self.calls.append(Call(task=task, payload=payload, body=body))
        answer = self._next(task)
        if isinstance(answer, Timeout):
            raise TimeoutError("scripted timeout")
        if isinstance(answer, HTTPStatus):
            raise urllib.error.HTTPError(
                "https://api.openai.com/v1/responses",
                answer.code,
                "scripted",
                {},
                _Response(answer.body.encode()),
            )
        if isinstance(answer, OSError):
            raise answer
        document = answer if isinstance(answer, dict) else envelope(answer)
        return _Response(json.dumps(document).encode())

    def calls_for(self, task: str) -> list[Call]:
        return [call for call in self.calls if call.task == task]

    def install(self, monkeypatch) -> FakeOpenAI:
        monkeypatch.setattr(urllib.request, "urlopen", self.urlopen)
        return self

    def provider(self, contracts, *, default_model: str = "gpt-test") -> OpenAIProvider:
        return OpenAIProvider(
            contracts,
            default_model=default_model,
            client_factory=lambda model: OpenAIResponsesProvider(model=model, api_key="test-key"),
        )
