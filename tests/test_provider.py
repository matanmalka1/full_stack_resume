"""The provider boundary: schema, parsing, sanitization, provenance, failures.

Everything here runs the real adapter stack over a scripted transport, so what
is asserted is production behavior at the seam a live call would cross. No test
in this file reaches the network, and none of them needs `OPENAI_API_KEY`.

Covers test-and-acceptance-plan §6 at the transport level: strict schema
generation for all five tasks, per-task Proposal parsing, refusal and
invalid-output handling, raw sanitization, and exact provider/model/usage/
latency/response metadata. The application-level items - semantic support, no
silent fallback, artifact registration, retries, injection - are in
`test_ai_tasks.py`, which drives the same adapter through Operations.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest
from fake_provider import FakeOpenAI, HTTPStatus, Timeout, envelope, refusal_envelope

from cv_engine.application.errors import (
    ProviderRateLimited,
    ProviderRefused,
    ProviderSchemaViolation,
    ProviderTimeout,
    ProviderUnavailable,
)
from cv_engine.application.ports import (
    DraftResumeContext,
    JobAnalysisContext,
    RegenerateClaimContext,
    RegenerateSectionContext,
    SelectionPlanContext,
)
from cv_engine.domain.models import (
    ClaimProposal,
    DraftProposal,
    JobClassificationProposal,
    ProposedClaim,
    SectionProposal,
    SelectionProposal,
)
from cv_engine.infrastructure.providers import (
    TASK_OUTPUT_MODELS,
)
from cv_engine.util import canonical_json, sha256_text

ANALYSIS_CONTEXT = JobAnalysisContext(
    job_text="...",
    deterministic_classification={"track": "sales"},
)
SELECTION_CONTEXT = SelectionPlanContext(
    job_analysis={"track": "sales"},
    allowed_facts=[{"fact_id": "a.b"}],
    deterministic_selection={"selected_fact_ids": ["a.b"]},
)
DRAFT_CONTEXT = DraftResumeContext(
    job_analysis={"track": "sales"},
    language="en",
    sections=[{"section": "Experience", "claims": []}],
    allowed_facts=[{"fact_id": "a.b"}],
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

CLASSIFICATION = JobClassificationProposal(
    track="sales",
    profile="account-manager",
    emphasis="account-growth",
    confidence=0.9,
    rationale="r",
    gaps=[],
    keywords=["k"],
)
SELECTION = SelectionProposal(pinned_fact_ids=["a.b"], excluded_fact_ids=[], rationale="r")
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

#: Every contracted task, its port method, its context, and its Proposal.
#: Read as a table so a sixth task cannot be added without appearing here - the
#: five-task coverage §6 asks for is then structural rather than remembered.
TASKS = [
    ("propose_job_analysis", ANALYSIS_CONTEXT, CLASSIFICATION),
    ("propose_selection_plan", SELECTION_CONTEXT, SELECTION),
    ("draft_resume", DRAFT_CONTEXT, DRAFT),
    ("regenerate_section", SECTION_CONTEXT, SECTION),
    ("regenerate_claim", CLAIM_CONTEXT, CLAIM),
]


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


def test_each_task_sends_a_strict_schema_and_parses_its_own_proposal(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: strict schema generation, and task-specific Proposal parsing."""
    assert set(task_contracts.tasks) == set(TASK_OUTPUT_MODELS)
    assert {name for name, _context, _proposal in TASKS} == set(TASK_OUTPUT_MODELS)
    provider = fake_openai.provider(task_contracts)
    for task, context, proposal in TASKS:
        fake_openai.script(task, proposal)
        answered = _call(provider, task, context)

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
        assert "previous_response_id" not in call.body
        assert "conversation" not in call.body

        nodes = _object_nodes(output_format["schema"])
        assert nodes, f"{task}: the generated schema declares no object"
        for path, node in nodes:
            assert node.get("additionalProperties") is False, f"{task}: {path} is open"
            assert sorted(node.get("required", [])) == sorted(node.get("properties", {})), (
                f"{task}: {path} leaves a property optional"
            )

        if task == "propose_job_analysis":
            assert {"fit", "language", "classification_requires_approval"}.isdisjoint(
                output_format["schema"]["properties"]
            )


def test_the_system_prompt_and_versions_come_from_the_contract_file(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: exact contract and prompt metadata, from one source.

    The prompt text in the request and the prompt hash in the provenance are
    both the contract file's, so a record can never name a prompt the call did
    not send.
    """
    fake_openai.script("propose_job_analysis", CLASSIFICATION)
    answered = _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)
    body = fake_openai.calls_for("propose_job_analysis")[-1].body
    assert body["input"][0]["content"] == task_contracts.prompt_text
    context = answered.provenance.context
    assert context.prompt_version == task_contracts.prompt_version
    assert context.prompt_hash == task_contracts.prompt_hash
    assert context.system_version == task_contracts.version
    contract = task_contracts.get("propose_job_analysis")
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
    sent = fake_openai.calls_for("propose_job_analysis")[-1].body["text"]["format"]["schema"]
    assert context.input_schema_hash == sha256_text(
        canonical_json(JobAnalysisContext.model_json_schema())
    )
    assert context.output_schema_hash == sha256_text(canonical_json(sent))
    assert context.provider == "openai"
    assert context.model == "gpt-test"
    assert context.response_id == "resp_fake_1"
    assert (context.usage.input_tokens, context.usage.output_tokens) == (11, 22)
    assert context.usage.total_tokens == 33
    assert context.latency_ms >= 0
    assert len(answered.provenance.input_hash) == 64
    assert len(answered.provenance.output_hash) == 64
    assert len(answered.provenance.raw_output_hash) == 64


def test_a_refusal_is_a_provider_refusal_carrying_its_own_evidence(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: refusal handling, with the answer kept as evidence."""
    fake_openai.script("propose_job_analysis", refusal_envelope())
    with pytest.raises(ProviderRefused) as raised:
        _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)
    provenance = raised.value.provenance
    assert provenance is not None
    assert "resp_fake_refusal" in provenance.sanitized_response
    # A refusal is exactly when "which model refused, under which contract"
    # has to be answerable, so the record is as complete as a success's.
    assert provenance.context.provider == "openai"
    assert provenance.context.model == "gpt-test"
    assert provenance.context.response_id == "resp_fake_refusal"
    assert provenance.output == {}


def test_invalid_output_is_a_schema_violation_and_never_a_partial_proposal(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: invalid-output handling.

    Including the case that matters most: an answer that adds a policy field.
    The Proposal model forbids extras, so a provider cannot smuggle `fit` in
    beside the fields it is allowed to send.
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
        fake_openai.scripts["propose_job_analysis"].clear()
        fake_openai.script("propose_job_analysis", envelope(text))
        with pytest.raises(ProviderSchemaViolation) as raised:
            _call(provider, "propose_job_analysis", ANALYSIS_CONTEXT)
        assert raised.value.provenance is not None, text
        assert raised.value.provenance.sanitized_response, text


def test_a_response_that_is_not_json_at_all_is_a_schema_violation(
    fake_openai: FakeOpenAI, task_contracts, monkeypatch
) -> None:
    class _Raw:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b"<html>gateway</html>"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _Raw())
    with pytest.raises(ProviderSchemaViolation):
        _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)


def test_transport_failures_are_classified_by_status_not_by_message(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """The classification a retry decision depends on, pinned to the status.

    Before Stage G this was decided by searching the exception message for
    "429", "timeout", and "http 5". A reworded message silently reclassified a
    failure, and only the transient four may be retried.
    """
    cases = [
        (HTTPStatus(429), ProviderRateLimited),
        (HTTPStatus(500), ProviderUnavailable),
        (HTTPStatus(503), ProviderUnavailable),
        (HTTPStatus(400), ProviderRefused),
        (HTTPStatus(401), ProviderRefused),
        (Timeout(), ProviderTimeout),
        (urllib.error.URLError("no route"), ProviderUnavailable),
    ]
    provider = fake_openai.provider(task_contracts)
    for answer, expected in cases:
        fake_openai.scripts["propose_job_analysis"].clear()
        fake_openai.script("propose_job_analysis", answer)
        with pytest.raises(expected):
            _call(provider, "propose_job_analysis", ANALYSIS_CONTEXT)
