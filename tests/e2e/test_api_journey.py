"""M3 §5.4 item 1: the whole sequence, through the API, offline.

Create -> Analyze -> Draft -> Edit -> Check -> Approve -> Render -> Ready -> Submit,
driven entirely over HTTP against a real FastAPI app, a real `OperationWorker`,
real PostgreSQL, and a real filesystem. This is the acceptance test the milestone
names, so it is deliberately one long test rather than several short ones: what
is being proved is that the steps compose, and a suite that proved each step
separately would not have proved that.

**`OPENAI_API_KEY` is asserted unset inside the test.** Not arranged - asserted.
The deterministic slice must reach Ready with no provider configured, and a test
that merely happened to run without a key would stop proving that the day a
developer exported one.

Three things it does *not* do, each for a stated reason:

- It does not stub the application layer anywhere. The only substitution is the
  browser, through `deterministic_renderer`, because Playwright is blocked by
  the OS sandbox this suite runs under; the render service, its Operation
  handler, and every registration are the real ones.
- It does not read the repository to decide what happened next. Every step is
  driven from the previous response, because that is what a client has.
- It does not skip the edit. §23's sequence has an Edit step, and a journey that
  went straight from draft to check would leave the ETag path unproven in the
  one test that is meant to prove the path end to end.
"""

from __future__ import annotations

import os

from api_harness import MUTATION_HEADERS
from fake_provider import FakeOpenAI
from helpers import (
    ACCOUNT_MANAGER_JOB,
    REVIEW_DECISION_JOB,
    analysis_proposal,
)

from cv_engine.api.app import API_PREFIX
from cv_engine.domain.analysis.projection import gaps
from cv_engine.domain.contracts.analysis_proposal import ProposedRequirement
from cv_engine.util import utc_now


def _post(harness, path: str, body: dict | None = None, **headers):
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body or {}, headers={**MUTATION_HEADERS, **headers}
    )


def _patch(harness, path: str, body: dict, **headers):
    return harness.client.patch(
        f"{API_PREFIX}{path}", json=body, headers={**MUTATION_HEADERS, **headers}
    )


def _get(harness, path: str):
    return harness.client.get(f"{API_PREFIX}{path}")


def _run_operation(harness, response, *, expect: str = "succeeded") -> dict:
    """Assert the `202` contract, then let the real worker finish the work."""
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert response.headers["Location"].endswith(accepted["id"])
    finished = harness.wait_for_operation(accepted["id"])
    assert finished["status"] == expect, finished
    return finished


def _outputs(finished: dict) -> dict[str, str]:
    return {output["output_type"]: output["output_id"] for output in finished["outputs"]}


def _reorder(outline: dict) -> dict:
    """A patch reversing the claims of the first section whose order is free to change."""
    section = next(
        item
        for item in outline["sections"]
        if len(item["claims"]) > 1
        and all(claim["style"] not in {"heading", "date"} for claim in item["claims"])
    )
    return {
        "claim_orders": {
            section["name"]: [claim["claim_id"] for claim in reversed(section["claims"])]
        }
    }


def _matched(quote: str, fact_id: str) -> ProposedRequirement:
    """One mandatory requirement, evidenced and matched."""
    return ProposedRequirement(
        text=quote,
        importance="mandatory",
        coverage="matched",
        fact_ids=[fact_id],
        rationale="stated in the posting",
    )


def _unsupported(quote: str) -> ProposedRequirement:
    """One mandatory requirement no fact evidences - a hard gap."""
    return ProposedRequirement(text=quote, importance="mandatory", coverage="unsupported")


def test_the_full_api_journey_reaches_ready_offline(
    ai_api_worker, fake_openai: FakeOpenAI, deterministic_renderer, monkeypatch
) -> None:
    """Offline means no real network call, not no provider at all.

    D5 (product-spec.md §2) requires a configured AI provider to create a
    JobAnalysis - there is no rules-based fallback. `ai_api_worker` answers
    Analyze through the fake OpenAI transport, so `OPENAI_API_KEY` still stays
    genuinely unset and nothing here reaches the network; only the step D5
    made provider-mandatory is scripted; everything downstream of the analysis
    - Draft through Ready - is exactly the deterministic slice this test
    proves runs with no key at all.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert os.environ.get("OPENAI_API_KEY") is None, (
        "the deterministic slice must reach Ready with no provider configured"
    )
    fake_openai.script(
        "propose_analysis",
        analysis_proposal(
            summary="account management role with a clear sales-cycle requirement",
            requirements=[
                _matched("Experience owning the full sales cycle.", "sales.summary.new_business"),
                _matched("Fluent English.", "common.language.english"),
            ],
        ),
    )

    # --- Create ---------------------------------------------------------
    created = _post(
        ai_api_worker,
        "/applications",
        {
            "company": "Journey Co",
            "target_role": "Account Manager",
            "job_text": ACCOUNT_MANAGER_JOB,
            "acknowledged_duplicates": True,
        },
    )
    assert created.status_code == 201, created.text
    application_id = created.json()["application_id"]
    job_snapshot_id = created.json()["job_snapshot_id"]
    document_path = f"/applications/{application_id}/document"

    detail = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "needs_analysis"
    assert _get(ai_api_worker, document_path).status_code == 404

    # --- Analyze --------------------------------------------------------
    analyzed = _run_operation(
        ai_api_worker,
        _post(
            ai_api_worker,
            f"/applications/{application_id}/analyses",
            {"job_snapshot_id": job_snapshot_id},
        ),
    )
    sources = _outputs(analyzed)
    # The first analysis creates the document with a deterministic selection and no
    # content, so the no-review path can draft without a separate selection command.
    detail = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "ready_to_draft"
    assert detail["document_id"] == sources["cv_document"]
    assert detail["document_analysis_id"] == sources["job_analysis"]

    read = _get(ai_api_worker, document_path)
    assert read.status_code == 200, read.text
    assert read.json()["content"] is None
    assert read.headers["ETag"] == f'"{detail["document_hash"]}"'
    token = read.json()["document_hash"]

    # --- Draft ----------------------------------------------------------
    drafted = _run_operation(
        ai_api_worker,
        _post(ai_api_worker, f"{document_path}/draft", {"expected_document_hash": token}),
    )
    assert _outputs(drafted)["cv_document"] == sources["cv_document"]

    detail = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "draft_in_progress"
    assert detail["document_state"] == "draft"

    read = _get(ai_api_worker, document_path)
    etag = read.headers["ETag"]
    assert read.json()["outline"] is not None

    # --- Edit -----------------------------------------------------------
    # A real edit: one section's claims reversed. The same patch is sent again below
    # with the old token, which makes that second save a real lost-update attempt.
    patch_body = _reorder(read.json()["outline"])

    edited = _patch(ai_api_worker, document_path, patch_body, **{"If-Match": etag})
    assert edited.status_code == 200, edited.text
    new_etag = edited.headers["ETag"]
    assert new_etag != etag
    token = edited.json()["document_hash"]
    assert new_etag == f'"{token}"'

    # The same token again is the concurrency matrix's first row: the second
    # save must change nothing at all rather than win or merge.
    stale = _patch(ai_api_worker, document_path, patch_body, **{"If-Match": etag})
    assert stale.status_code == 409, stale.text
    assert _get(ai_api_worker, document_path).headers["ETag"] == new_etag

    # --- Check ----------------------------------------------------------
    checked = _post(ai_api_worker, f"{document_path}/check", {"expected_document_hash": token})
    assert checked.status_code == 200, checked.text
    assert checked.json()["passed"] is True, checked.json()["report"]
    assert checked.json()["content_check"] == "passed"
    assert checked.json()["document_state"] == "draft"

    # --- Approve --------------------------------------------------------
    approved = _post(ai_api_worker, f"{document_path}/approve", {"expected_document_hash": token})
    assert approved.status_code == 200, approved.text
    assert approved.json()["passed"] is True
    assert approved.json()["approved_at"] is not None

    detail = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "approved"
    assert detail["approved_at"] == approved.json()["approved_at"]
    # Nothing is rendered yet, so there is nothing to hand a recruiter.
    assert _get(ai_api_worker, f"{document_path}/pdf").status_code == 412

    # --- Render ---------------------------------------------------------
    rendered = _run_operation(
        ai_api_worker,
        _post(ai_api_worker, f"{document_path}/render", {"expected_document_hash": token}),
    )
    assert _outputs(rendered)["cv_document"] == sources["cv_document"]

    # --- Ready ----------------------------------------------------------
    detail = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "ready"
    assert detail["document_state"] == "ready"
    assert detail["document_hash"] == token

    # --- Download the Ready PDF (§16) -----------------------------------
    export = _get(ai_api_worker, f"{document_path}/pdf")
    assert export.status_code == 200, export.text
    assert export.content.startswith(b"%PDF")
    assert "CV.pdf" in export.headers["content-disposition"]
    assert export.headers["ETag"] == f'"{token}"'

    # --- Submit (§18) ---------------------------------------------------
    submitted = _post(
        ai_api_worker,
        f"/applications/{application_id}/submissions",
        {"expected_document_hash": token, "submitted_at": utc_now()},
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["document_hash"] == token

    # --- The way back ---------------------------------------------------
    # Ready is derived, not a frozen revision: an edit returns the document to the
    # draft step, and the PDF is refused until it is approved and rendered again.
    reorder = _reorder(_get(ai_api_worker, document_path).json()["outline"])
    back = _patch(ai_api_worker, document_path, reorder, **{"If-Match": f'"{token}"'})
    assert back.status_code == 200, back.text
    detail = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert detail["preparation_state"] == "draft_in_progress"
    # The stored approval no longer approves anything, so its time is not reported.
    assert detail["approved_at"] is None
    assert _get(ai_api_worker, document_path).json()["approved_at"] is None
    assert _get(ai_api_worker, f"{document_path}/pdf").status_code == 412


def test_the_review_journey_resolves_once_and_reaches_ready(
    ai_api_worker,
    fake_openai: FakeOpenAI,
    deterministic_renderer,
    transaction_manager,
    application_projection_reader,
) -> None:
    fake_openai.script(
        "propose_analysis",
        analysis_proposal(
            summary="account management with an unverified SaaS-specific requirement",
            requirements=[
                _matched("Experience owning the full sales cycle.", "sales.summary.new_business"),
                _unsupported("Sales experience at a SaaS company."),
            ],
        ),
    )
    created = _post(
        ai_api_worker,
        "/applications",
        {
            "company": "Review Journey Co",
            "target_role": "Account Manager",
            "job_text": REVIEW_DECISION_JOB,
            "acknowledged_duplicates": True,
        },
    )
    assert created.status_code == 201, created.text
    application_id = created.json()["application_id"]
    document_path = f"/applications/{application_id}/document"

    analyzed = _run_operation(
        ai_api_worker,
        _post(
            ai_api_worker,
            f"/applications/{application_id}/analyses",
            {"job_snapshot_id": created.json()["job_snapshot_id"]},
        ),
    )
    original = _outputs(analyzed)

    # The posting demands SaaS sales the candidate cannot show. The gap is found and
    # marked hard; it is shown, and drafting is open without a decision.
    state = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert state["review_reasons"] == []
    assert state["preparation_state"] == "ready_to_draft"
    assert state["latest_analysis"]["fit_level"] == "low"
    assert [gap["severity"] for gap in state["latest_analysis"]["gaps"]] == ["hard"]
    assert {"fit", "fit_level", "fit_score", "gaps"}.isdisjoint(
        state["latest_analysis"]["analysis"]
    )
    with transaction_manager.read() as tx:
        analysis = application_projection_reader.analysis(tx, original["job_analysis"])["analysis"]
    assert [
        gap.severity
        for gap in gaps(analysis.requirements, ai_api_worker.services.knowledge.facts())
    ] == ["hard"]

    token = state["document_hash"]
    _run_operation(
        ai_api_worker,
        _post(ai_api_worker, f"{document_path}/draft", {"expected_document_hash": token}),
    )
    token = _get(ai_api_worker, document_path).json()["document_hash"]

    approved = _post(ai_api_worker, f"{document_path}/approve", {"expected_document_hash": token})
    assert approved.status_code == 200, approved.text
    assert approved.json()["passed"] is True, approved.json()["report"]

    _run_operation(
        ai_api_worker,
        _post(ai_api_worker, f"{document_path}/render", {"expected_document_hash": token}),
    )
    state = _get(ai_api_worker, f"/applications/{application_id}").json()
    assert state["preparation_state"] == "ready"
