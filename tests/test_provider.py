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
    _strict_schema,
    sanitize_response,
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


def test_every_contracted_task_has_exactly_one_output_model(task_contracts) -> None:
    """The contract file and the adapter's task table cannot drift apart."""
    assert set(task_contracts.tasks) == set(TASK_OUTPUT_MODELS)
    assert {name for name, _context, _proposal in TASKS} == set(TASK_OUTPUT_MODELS)


def test_the_strict_rewrite_actually_changes_the_hashed_document() -> None:
    """The reason the output hash is taken from the request, made to fail loudly.

    `SelectionProposal` declares one required field and comes back with three
    after `_strict_schema`. If that ever stopped being true, hashing the model
    and hashing the sent schema would agree, and the distinction the provenance
    draws would be untested rather than merely unnecessary.
    """
    raw = SelectionProposal.model_json_schema()
    strict = _strict_schema(raw)
    assert sorted(raw.get("required", [])) != sorted(strict["required"])
    assert canonical_json(raw) != canonical_json(strict)


def test_every_task_declares_both_schema_versions(task_contracts) -> None:
    """Architecture §11 names input *and* output schema versions.

    Read from the contract file over the adapter's task table, so a task added
    to the code without declaring its schema versions fails here rather than
    persisting an empty string into an immutable record.
    """
    for name, model in TASK_OUTPUT_MODELS.items():
        contract = task_contracts.get(name)
        assert contract.input, name
        assert contract.output == model.__name__, name
        assert contract.input_schema_version, name
        assert contract.output_schema_version, name


@pytest.mark.parametrize("task,context,proposal", TASKS, ids=[item[0] for item in TASKS])
def test_each_task_sends_a_strict_schema_and_parses_its_own_proposal(
    fake_openai: FakeOpenAI, task_contracts, task, context, proposal
) -> None:
    """§6: strict schema generation, and task-specific Proposal parsing."""
    fake_openai.script(task, proposal)
    answered = _call(fake_openai.provider(task_contracts), task, context)

    assert answered.proposal == proposal
    assert type(answered.proposal) is TASK_OUTPUT_MODELS[task]

    body = fake_openai.calls_for(task)[-1].body
    output_format = body["text"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["name"] == task
    assert output_format["strict"] is True

    # The contract file names the models on both sides. Compared against what
    # actually crossed, so a wrong name in the file fails here instead of being
    # persisted as a truthful-looking `*_schema_version`.
    contract = task_contracts.get(task)
    assert contract.input == type(context).__name__
    assert contract.output == type(answered.proposal).__name__

    # Strict Structured Outputs requires every declared property to be required
    # and every object closed - at every depth, not only at the root.
    nodes = _object_nodes(output_format["schema"])
    assert nodes, "the generated schema declares no object at all"
    for path, node in nodes:
        assert node.get("additionalProperties") is False, f"{task}: {path} is open"
        assert sorted(node.get("required", [])) == sorted(node.get("properties", {})), (
            f"{task}: {path} leaves a property optional"
        )


def test_a_nested_proposal_model_is_reached_by_the_strict_walk() -> None:
    """The walk is only worth having if a task actually nests a model.

    `DraftProposal` does - `claims` is a list of `ProposedClaim`. Asserted
    directly so that if the Proposal shapes are ever flattened, this fails and
    says the recursive check has stopped proving anything, rather than passing
    over a document with nothing below the root.
    """
    schema = _strict_schema(DraftProposal.model_json_schema())
    paths = [path for path, _node in _object_nodes(schema)]
    assert any("$defs" in path for path in paths), paths
    assert schema["$defs"]["ProposedClaim"]["additionalProperties"] is False


def test_the_classification_schema_cannot_express_a_policy_field(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """The proposal contract is narrower than `JobAnalysis`, by construction."""
    fake_openai.script("propose_job_analysis", CLASSIFICATION)
    _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)
    properties = fake_openai.calls_for("propose_job_analysis")[-1].body["text"]["format"]["schema"][
        "properties"
    ]
    assert {"fit", "language", "classification_requires_approval"}.isdisjoint(properties)


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


def test_provenance_records_provider_model_usage_latency_and_response_id(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: exact provider/model/usage/latency/response metadata."""
    fake_openai.script("propose_job_analysis", CLASSIFICATION)
    answered = _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)
    context = answered.provenance.context
    assert context.provider == "openai"
    assert context.model == "gpt-test"
    assert context.response_id == "resp_fake_1"
    assert (context.usage.input_tokens, context.usage.output_tokens) == (11, 22)
    assert context.usage.total_tokens == 33
    assert context.latency_ms >= 0
    assert len(answered.provenance.input_hash) == 64
    assert len(answered.provenance.output_hash) == 64
    assert len(answered.provenance.raw_output_hash) == 64


def test_the_preserved_response_is_the_sanitized_one_and_its_hash_matches(
    fake_openai: FakeOpenAI, task_contracts
) -> None:
    """§6: raw response sanitization.

    Secrets and hidden reasoning are gone, the hash covers what is preserved,
    and the structured answer itself survives - a sanitizer that removed the
    output would leave an artifact proving nothing.
    """
    dirty = envelope(
        CLASSIFICATION,
        api_key="sk-live-should-never-be-stored",
        reasoning={"summary": "hidden chain of thought"},
    )
    dirty["output"].insert(0, {"type": "reasoning", "summary": ["step one", "step two"]})
    dirty["output"][1]["Authorization"] = "Bearer sk-live"
    fake_openai.script("propose_job_analysis", dirty)

    answered = _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)
    preserved = answered.provenance.sanitized_response

    for secret in ("sk-live", "hidden chain of thought", "step one", "Bearer"):
        assert secret not in preserved
    assert '"reasoning"' not in preserved
    assert "account-manager" in preserved
    assert answered.provenance.raw_output_hash == sha256_text(preserved)


def test_sanitization_removes_secret_keys_at_any_depth() -> None:
    cleaned = sanitize_response(
        {
            "keep": "yes",
            "nested": {"Access-Token": "t", "deeper": [{"password": "p", "keep": 1}]},
            "output": [{"type": "reasoning", "summary": "drop"}, {"type": "message"}],
        }
    )
    assert cleaned == {
        "keep": "yes",
        "nested": {"deeper": [{"keep": 1}]},
        "output": [{"type": "message"}],
    }


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


@pytest.mark.parametrize(
    "text",
    [
        '{"track": "sales"}',
        '{"track": "sales", "profile": "account-manager", "emphasis": "account-growth",'
        ' "confidence": 0.9, "rationale": "r", "gaps": [], "keywords": ["k"],'
        ' "fit": "high"}',
        "not json at all",
    ],
    ids=["missing-fields", "extra-policy-field", "not-json"],
)
def test_invalid_output_is_a_schema_violation_and_never_a_partial_proposal(
    fake_openai: FakeOpenAI, task_contracts, text
) -> None:
    """§6: invalid-output handling.

    Including the case that matters most: an answer that adds a policy field.
    The Proposal model forbids extras, so a provider cannot smuggle `fit` in
    beside the fields it is allowed to send.
    """
    fake_openai.script("propose_job_analysis", envelope(text))
    with pytest.raises(ProviderSchemaViolation) as raised:
        _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)
    assert raised.value.provenance is not None
    assert raised.value.provenance.sanitized_response


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


@pytest.mark.parametrize(
    "answer,expected",
    [
        (HTTPStatus(429), ProviderRateLimited),
        (HTTPStatus(500), ProviderUnavailable),
        (HTTPStatus(503), ProviderUnavailable),
        (HTTPStatus(400), ProviderRefused),
        (HTTPStatus(401), ProviderRefused),
        (Timeout(), ProviderTimeout),
        (urllib.error.URLError("no route"), ProviderUnavailable),
    ],
    ids=["429", "500", "503", "400", "401", "timeout", "network"],
)
def test_transport_failures_are_classified_by_status_not_by_message(
    fake_openai: FakeOpenAI, task_contracts, answer, expected
) -> None:
    """The classification a retry decision depends on, pinned to the status.

    Before Stage G this was decided by searching the exception message for
    "429", "timeout", and "http 5". A reworded message silently reclassified a
    failure, and only the transient four may be retried.
    """
    fake_openai.script("propose_job_analysis", answer)
    with pytest.raises(expected):
        _call(fake_openai.provider(task_contracts), "propose_job_analysis", ANALYSIS_CONTEXT)


def test_each_task_receives_only_its_own_context(fake_openai: FakeOpenAI, task_contracts) -> None:
    """§6: stateless inputs and minimal context.

    Nothing is carried between calls: no conversation, no prior response ID, no
    accumulated history. Two calls to different tasks send exactly their own
    contexts and nothing else.
    """
    provider = fake_openai.provider(task_contracts)
    fake_openai.script("propose_job_analysis", CLASSIFICATION)
    fake_openai.script("regenerate_claim", CLAIM)
    _call(provider, "propose_job_analysis", ANALYSIS_CONTEXT)
    _call(provider, "regenerate_claim", CLAIM_CONTEXT)

    for call in fake_openai.calls:
        assert [message["role"] for message in call.body["input"]] == ["system", "user"]
        assert "previous_response_id" not in call.body
        assert "conversation" not in call.body
    assert fake_openai.calls_for("propose_job_analysis")[-1].payload == ANALYSIS_CONTEXT.model_dump(
        mode="json"
    )
    assert fake_openai.calls_for("regenerate_claim")[-1].payload == CLAIM_CONTEXT.model_dump(
        mode="json"
    )
