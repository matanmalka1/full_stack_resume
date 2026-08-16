from __future__ import annotations

import json
import urllib.request

from cv_engine.analysis import classify_job
from cv_engine.models import JobAnalysis
from cv_engine.providers import OpenAIResponsesProvider


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.body


def test_openai_responses_adapter_uses_strict_schema_and_validates_output(monkeypatch) -> None:
    proposal = classify_job("Python backend developer API React")
    envelope = {
        "output": [{"content": [{"type": "output_text", "text": proposal.model_dump_json()}]}]
    }
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _Response(json.dumps(envelope).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAIResponsesProvider(model="gpt-test", api_key="test-key")
    parsed, provenance = provider.run("classify_job", {"job_text": "..."}, JobAnalysis)
    assert parsed == proposal
    assert provenance.context.provider == "openai"
    output_format = captured["body"]["text"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    assert output_format["schema"]["additionalProperties"] is False
