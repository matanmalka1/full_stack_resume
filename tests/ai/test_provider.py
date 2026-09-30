"""The provider boundary: schema, parsing, sanitization, provenance, failures.

Everything here runs the real adapter stack over a scripted transport, so what
is asserted is production behavior at the seam a live call would cross. No test
in this file reaches the network, and none of them needs `OPENAI_API_KEY`.

Covers test-and-acceptance-plan §6 at the transport level: strict schema
generation for every contracted task, per-task Proposal parsing, refusal and
invalid-output handling, sanitization, the classification of every attempt's
outcome, and exact provider/model/usage/cost/latency/response metadata. Each call
is one attempt returned as a record, never an exception. The application-level
items - semantic support, no silent fallback, the AI call log, retries,
injection - are in `test_ai_tasks.py`, which drives the same adapter through
Operations.
"""

from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest
from fake_provider import FakeOpenAI, HTTPStatus, Timeout, envelope, refusal_envelope

from cv_engine.application.ai_configuration import execution_cost
from cv_engine.application.ports import (
    AnalysisContext,
    AssessClaimSupportContext,
    DraftResumeContext,
    RegenerateClaimContext,
    RegenerateSectionContext,
)
from cv_engine.domain.contracts.analysis_proposal import AnalysisProposal
from cv_engine.domain.contracts.providers import (
    ClaimProposal,
    ClaimSupportAssessment,
    ClaimSupportProposal,
    DraftProposal,
    ProposedClaim,
    SectionProposal,
)
from cv_engine.domain.contracts.taxonomy import Emphasis, ProfileName, Track
from cv_engine.infrastructure.providers import TASK_OUTPUT_MODELS
from cv_engine.util import canonical_json, sha256_text

ANALYSIS_CONTEXT = AnalysisContext(
    job_text="...",
    candidate_facts=[],
)

DRAFT_CONTEXT = DraftResumeContext(
    job_analysis={"track": "sales"},
    job_text="Account manager role",
    requirements=[],
    language="en",
    sections=[{"section": "Experience", "allowed_fact_ids": ["a.b"], "claims": []}],
    allowed_facts=[{"fact_id": "a.b"}],
    guidance={"required_tags": []},
)
REVIEW_CONTEXT = AssessClaimSupportContext(
    language="en",
    claims=[{"claim_id": "c1", "section": "Experience", "text": "t", "fact_ids": ["a.b"]}],
    allowed_facts=[{"fact_id": "a.b", "meaning": "t", "rendering": "t"}],
)
SECTION_CONTEXT = RegenerateSectionContext(
    section="Experience",
    language="en",
    job_analysis={"track": "sales"},
    current_claims=[],
    allowed_facts=[{"fact_id": "a.b"}],
)
CLAIM_CONTEXT = RegenerateClaimContext(
    claim_id="c1",
    section="Experience",
    language="en",
    job_analysis={"track": "sales"},
    current_text="old",
    allowed_facts=[{"fact_id": "a.b"}],
)

ANALYSIS = AnalysisProposal(
    track=Track.SALES,
    profile=ProfileName.ACCOUNT_MANAGER,
    emphasis=Emphasis.ACCOUNT_GROWTH,
    language="en",
    requirements=[],
    summary="r",
    keywords=["k"],
)
DRAFT = DraftProposal(
    claims=[ProposedClaim(section="Experience", claim_id="c1", text="t", fact_ids=["a.b"])],
    rationale="r",
)
SECTION = SectionProposal(
    section="Experience",
    claims=[ProposedClaim(section="Experience", claim_id="c1", text="t", fact_ids=["a.b"])],
    rationale="r",
)
CLAIM = ClaimProposal(claim_id="c1", text="t", fact_ids=["a.b"], rationale="r")
REVIEW = ClaimSupportProposal(
    assessments=[
        ClaimSupportAssessment(claim_id="c1", verdict="supported", assertions=[], rationale="r")
    ]
)

#: Every contracted task, its port method, its context, and its Proposal.
#: Read as a table so a new task cannot be added without appearing here -
#: coverage of every task §6 asks for is then structural rather than
#: remembered.
TASKS = [
    ("propose_analysis", ANALYSIS_CONTEXT, ANALYSIS),
    ("draft_resume", DRAFT_CONTEXT, DRAFT),
    ("assess_claim_support", REVIEW_CONTEXT, REVIEW),
    ("regenerate_section", SECTION_CONTEXT, SECTION),
    ("regenerate_claim", CLAIM_CONTEXT, CLAIM),
]


def test_long_context_cost_uses_the_pricing_snapshot_multipliers() -> None:
    assert execution_cost(
        "gpt-5.6-terra",
        input_tokens=300_000,
        cached_input_tokens=0,
        cache_write_tokens=0,
        output_tokens=1_000,
    ) == {
        "input_usd": "1.20000000",
        "output_usd": "0.01800000",
        "total_usd": "1.21800000",
    }


@pytest.mark.parametrize(
    ("cached", "written", "input_usd"),
    [
        # 1,000 ordinary input tokens at $2.00 per million.
        (0, 0, "0.00200000"),
        # Cache read: 400 at $0.20 and 600 ordinary at $2.00.
        (400, 0, "0.00128000"),
        # Cache write: 400 at 1.25 x $2.00 and 600 ordinary at $2.00.
        (0, 400, "0.00220000"),
        # Both: 300 read, 200 written, 500 ordinary.
        (300, 200, "0.00156000"),
    ],
)
def test_input_is_billed_once_as_ordinary_cached_or_cache_write(cached, written, input_usd):
    """Every input token has exactly one rate: ordinary = input - cached - cache_write."""
    cost = execution_cost(
        "gpt-5.6-terra",
        input_tokens=1_000,
        cached_input_tokens=cached,
        cache_write_tokens=written,
        output_tokens=0,
    )
    assert cost is not None
    assert cost["input_usd"] == input_usd


def test_a_cost_that_needs_cache_writes_is_unknown_without_them() -> None:
    """GPT-5.6 prices cache writes, so a usage without that count cannot be priced."""
    assert (
        execution_cost(
            "gpt-5.6-terra",
            input_tokens=1_000,
            cached_input_tokens=0,
            cache_write_tokens=None,
            output_tokens=10,
        )
        is None
    )
    with pytest.raises(ValueError, match="inconsistent"):
        execution_cost(
            "gpt-5.6-terra",
            input_tokens=10,
            cached_input_tokens=8,
            cache_write_tokens=5,
            output_tokens=0,
        )


def _call(provider, task, context):
    return getattr(provider, task)(context)


def _object_nodes(schema: dict) -> list[tuple[str, dict]]:
    """Every object node in a JSON Schema, `$defs` and nested arrays included.

    Strict Structured Outputs applies to the whole document, not to its root:
    `DraftProposal` declares `claims: list[ProposedClaim]`, so the node that
    would actually let a provider smuggle an extra field is `$defs.ProposedClaim`
    - two levels below anything a top-level assertion can see.

    Walked rather than listed, so a Proposal that grows a nested model is
    covered the day it is written.
    """
    found: list[tuple[str, dict]] = []

    def visit(node, path: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                found.append((path, node))
            for key, value in node.items():
                visit(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                visit(value, f"{path}[{index}]")

    visit(schema, "$")
    return found


def test_prompt_directory_holds_only_the_declared_prompt() -> None:
    """A superseded prompt is deleted, not kept beside the live one (README)."""
    root = Path(__file__).resolve().parents[2]
    contracts = json.loads((root / "ai/contracts/task_contracts.json").read_text("utf-8"))
    present = {
        path.relative_to(root).as_posix()
        for path in (root / "ai/prompts").iterdir()
        if not path.name.startswith(".")
    }
    assert present == {contracts["prompt"]["file"]}


def test_each_task_sends_a_strict_schema_and_parses_its_own_proposal(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: strict schema generation, and task-specific Proposal parsing."""
    assert set(task_contracts.tasks) == set(TASK_OUTPUT_MODELS)
    assert {name for name, _context, _proposal in TASKS} == set(TASK_OUTPUT_MODELS)
    assert {"propose_requirement_extraction", "propose_job_analysis"}.isdisjoint(
        task_contracts.tasks
    )
    provider = fake_openai.provider(task_contracts)
    for task, context, proposal in TASKS:
        fake_openai.script(task, proposal)
        answered = _call(provider, task, context)

        assert answered.record.outcome == "succeeded", task
        assert answered.proposal == proposal, task
        assert type(answered.proposal) is TASK_OUTPUT_MODELS[task]

        body = fake_openai.calls_for(task)[-1].body
        output_format = body["text"]["format"]
        assert output_format["type"] == "json_schema", task
        assert output_format["name"] == task
        assert output_format["strict"] is True

        contract = task_contracts.get(task)
        assert contract.input == type(context).__name__
        assert contract.output == type(answered.proposal).__name__
        assert contract.input_schema_version, task
        assert contract.output_schema_version, task

        call = fake_openai.calls_for(task)[-1]
        assert call.payload == context.model_dump(mode="json"), task
        assert [message["role"] for message in call.body["input"]] == ["system", "user"]
        assert call.body["reasoning"] == {"effort": "medium"}
        assert "previous_response_id" not in call.body
        assert "conversation" not in call.body

        nodes = _object_nodes(output_format["schema"])
        assert nodes, f"{task}: the generated schema declares no object"
        for path, node in nodes:
            assert node.get("additionalProperties") is False, f"{task}: {path} is open"
            assert sorted(node.get("required", [])) == sorted(node.get("properties", {})), (
                f"{task}: {path} leaves a property optional"
            )

        if task == "propose_analysis":
            # The fields that route safety decisions stay out of provider
            # reach: Fit and approval routing are derived from the requirements
            # the engine kept, never reported.
            assert {"fit", "fit_score", "gaps", "approval_reasons", "issues"}.isdisjoint(
                output_format["schema"]["properties"]
            )
            requirement_schema = output_format["schema"]["$defs"]["ProposedRequirement"]
            assert {
                "coverage",
                "shortfall_severity",
                "shortfall_reason",
            } <= requirement_schema["properties"].keys()


def test_the_system_prompt_and_versions_come_from_the_contract_file(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: exact contract and prompt metadata, from one source.

    The prompt text in the request and the prompt hash in the provenance are
    both the contract file's, so a record can never name a prompt the call did
    not send.
    """
    fake_openai.script("propose_analysis", ANALYSIS)
    answered = _call(fake_openai.provider(task_contracts), "propose_analysis", ANALYSIS_CONTEXT)
    body = fake_openai.calls_for("propose_analysis")[-1].body
    assert body["input"][0]["content"] == task_contracts.prompt_text
    context = answered.record
    assert context.prompt_version == task_contracts.prompt_version
    assert context.prompt_hash == task_contracts.prompt_hash
    contract = task_contracts.get("propose_analysis")
    assert context.task_contract_version == contract.version
    assert context.input_schema_version == contract.input_schema_version
    assert context.output_schema_version == contract.output_schema_version
    # The declared version is a label; the hash is derived from the schema that
    # actually governed the boundary, so the two cannot silently disagree.
    #
    # The two sides hash different documents on purpose. No input schema is
    # transmitted, so the input hash is the context model's own. The output
    # schema *is* transmitted, and `_strict_schema` rewrote it on the way out -
    # so the hash has to be of the document in the request, not of the model it
    # was derived from.
    sent = fake_openai.calls_for("propose_analysis")[-1].body["text"]["format"]["schema"]
    assert context.input_schema_hash == sha256_text(
        canonical_json(AnalysisContext.model_json_schema())
    )
    assert context.output_schema_hash == sha256_text(canonical_json(sent))
    assert context.provider == "openai"
    assert context.model == "gpt-5.6-terra"
    assert context.reasoning_effort == "medium"
    assert context.response_id == "resp_fake_1"
    assert (context.usage.input_tokens, context.usage.output_tokens) == (11, 22)
    assert context.usage.cached_input_tokens == 3
    assert context.usage.cache_write_tokens == 0
    assert context.usage.total_tokens == 33
    assert context.pricing is not None
    assert context.pricing.version == "openai-2026-09-30"
    assert context.cost is not None
    assert context.cost.total_usd == "0.00028060"
    assert context.latency_ms >= 0
    assert context.started_at <= context.finished_at
    assert context.input_hash == sha256_text(
        canonical_json(ANALYSIS_CONTEXT.model_dump(mode="json"))
    )
    assert context.output_hash == sha256_text(canonical_json(ANALYSIS.model_dump(mode="json")))
    # The evidence is the sanitized envelope in canonical form, hashed as such.
    assert context.sanitized_response is not None
    assert context.sanitized_response["id"] == "resp_fake_1"
    assert context.sanitized_response_hash == sha256_text(
        canonical_json(context.sanitized_response)
    )

    # The rules the tasks rely on are in that one prompt. Analysis splits a
    # sentence only into self-contained quotes and judges qualitative and
    # frequency wording semantically; drafting chooses by keeping claims, weighs guidance
    # without treating it as fact, and cites only each section's allowed facts.
    prompt = task_contracts.prompt_text
    for rule in (
        "return each as its own requirement only if every one of them can be quoted",
        "Keep any qualifier that applies to a given piece",
        "keep the sentence as one requirement instead",
        "Judge qualitative wording",
        "Do not require a fact to",
        "Absence of that wording or quantification is not by itself",
        "identifiable substantive condition",
        "frequency or habit wording",
        "explicit duration or quantity threshold",
        "Return only the claims you keep",
        "a heading left without one fails the draft",
        "never license wording the kept facts do not support",
        "Each section names its `allowed_fact_ids`",
        "A fact absent from this section's `allowed_fact_ids`",
    ):
        assert rule in prompt, rule


def test_a_refusal_is_an_attempt_record_as_complete_as_a_success(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: refusal handling. The attempt comes back as a record, never an exception."""
    fake_openai.script("propose_analysis", refusal_envelope())
    answered = _call(fake_openai.provider(task_contracts), "propose_analysis", ANALYSIS_CONTEXT)
    record = answered.record
    assert answered.proposal is None
    assert record.outcome == "refused"
    # A refusal is exactly when "which model refused, under which contract"
    # has to be answerable, so the record is as complete as a success's.
    assert record.provider == "openai"
    assert record.model == "gpt-5.6-terra"
    assert record.response_id == "resp_fake_refusal"
    assert record.sanitized_response is not None
    assert record.output_hash is None
    # Its usage leaves out the cached count, so usage and cost are unknown, not zero.
    assert (record.usage, record.cost) == (None, None)


def test_invalid_output_is_a_schema_violation_and_never_a_partial_proposal(
    fake_openai: FakeOpenAI, task_contracts, monkeypatch
) -> None:
    """§6: invalid-output handling.

    Including the case that matters most: an answer that adds a policy field.
    The Proposal model forbids extras, so a provider cannot smuggle `fit` in
    beside the fields it is allowed to send. A body that is not a Responses
    envelope at all - a gateway's HTML page - is the same violation, kept as text.
    """
    texts = [
        '{"track": "sales"}',
        '{"track": "sales", "profile": "account-manager", "emphasis": "account-growth",'
        ' "confidence": 0.9, "rationale": "r", "gaps": [], "keywords": ["k"],'
        ' "fit": "high"}',
        "not json at all",
    ]
    provider = fake_openai.provider(task_contracts)
    for text in texts:
        fake_openai.scripts["propose_analysis"].clear()
        fake_openai.script("propose_analysis", envelope(text))
        answered = _call(provider, "propose_analysis", ANALYSIS_CONTEXT)
        assert answered.proposal is None, text
        assert answered.record.outcome == "schema_violation", text
        assert answered.record.sanitized_response, text
        assert answered.record.usage is not None, text

    class _Raw:
        status = 200
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b"<html>gateway Bearer sk-live-abcdefgh1234</html>"

    _Raw.headers["Content-Type"] = "text/html"
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _Raw())
    answered = _call(fake_openai.provider(task_contracts), "propose_analysis", ANALYSIS_CONTEXT)
    assert answered.record.outcome == "schema_violation"
    kept = answered.record.sanitized_response
    assert kept is not None
    assert kept["content_type"] == "text/html"
    assert kept["truncated"] is False
    assert "sk-live" not in kept["body_text"] and "[redacted]" in kept["body_text"]


@pytest.mark.parametrize(
    ("answer", "outcome", "error_type", "error_code", "retry_after"),
    [
        (
            HTTPStatus(429, headers=(("Retry-After", "2"),)),
            "rate_limited",
            None,
            None,
            2.0,
        ),
        (HTTPStatus(429), "rate_limited", None, None, None),
        (
            HTTPStatus(
                429,
                body='{"error": {"type": "rate_limit_error", "code": "slow_down"}}',
                headers=(("Retry-After", "Wed, 21 Oct 2015 07:28:00 GMT"),),
            ),
            "rate_limited",
            "rate_limit_error",
            "slow_down",
            0.0,
        ),
        (
            HTTPStatus(429, body='{"error": {"code": "credit_balance_exhausted"}}'),
            "quota_exhausted",
            None,
            "credit_balance_exhausted",
            None,
        ),
        (
            HTTPStatus(429, body='{"error": {"type": "insufficient_quota"}}'),
            "quota_exhausted",
            "insufficient_quota",
            None,
            None,
        ),
        (HTTPStatus(500), "http_error", None, None, None),
        (HTTPStatus(503, headers=(("Retry-After", "5"),)), "http_error", None, None, 5.0),
        (HTTPStatus(400), "http_error", None, None, None),
        (HTTPStatus(401), "http_error", None, None, None),
        # Provably never sent: no name to connect to, or a connection refused.
        (
            urllib.error.URLError(socket.gaierror(-2, "no name")),
            "not_delivered",
            "gaierror",
            None,
            None,
        ),
        (
            urllib.error.URLError(ConnectionRefusedError(111, "refused")),
            "not_delivered",
            "ConnectionRefusedError",
            None,
            None,
        ),
        # Wrapped, but possibly after the request was on the wire.
        (urllib.error.URLError(TimeoutError()), "outcome_unknown", "TimeoutError", None, None),
        (
            urllib.error.URLError(ConnectionResetError()),
            "outcome_unknown",
            "ConnectionResetError",
            None,
            None,
        ),
        (urllib.error.URLError("no route"), "outcome_unknown", "URLError", None, None),
        # Raised while waiting for or reading the answer: the request was sent.
        (Timeout(), "outcome_unknown", "TimeoutError", None, None),
        (ConnectionResetError(), "outcome_unknown", "ConnectionResetError", None, None),
        (http.client.RemoteDisconnected(), "outcome_unknown", "RemoteDisconnected", None, None),
        (http.client.IncompleteRead(b""), "outcome_unknown", "IncompleteRead", None, None),
    ],
)
def test_every_attempt_outcome_is_classified_from_its_evidence_not_a_message(
    fake_openai: FakeOpenAI, task_contracts, answer, outcome, error_type, error_code, retry_after
) -> None:
    """Classified by status, error code and failure stage - never by a message.

    `urlopen` wraps connect *and send* failures alike in `URLError`, so only a failed
    name lookup or a refused connection proves nothing was sent. Every other
    transport failure may have reached the provider, which may have billed it.
    """
    fake_openai.script("propose_analysis", answer)
    answered = _call(fake_openai.provider(task_contracts), "propose_analysis", ANALYSIS_CONTEXT)
    record = answered.record
    assert answered.proposal is None
    assert record.outcome == outcome
    assert record.error_type == error_type
    assert record.error_code == error_code
    assert record.retry_after_seconds == retry_after
    assert (record.usage, record.cost) == (None, None)
    if isinstance(answer, HTTPStatus):
        assert record.http_status == answer.code
        assert record.sanitized_response is not None
    else:
        assert record.http_status is None
        assert record.sanitized_response is None
