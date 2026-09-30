"""Render, and the document's files over HTTP.

Two things here are the point, and the rest is scaffolding around them.

**A render failure changes nothing about the approval.** The failure lands on the
Operation and on `last_render_error`; the approval stamp, the active files and the
document's hash are read back and compared, not one status string.

**The PDF is answered for what is Ready now.** The document's rendered files are
mutable working outputs, not registered artifacts, so the download checks the basis
when it answers and refuses anything that is not Ready at that moment.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS
from helpers import stored_document

from cv_engine.api.app import API_PREFIX


def _post(harness, path: str, body: dict | None = None, **headers):
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body or {}, headers={**MUTATION_HEADERS, **headers}
    )


def _get(harness, path: str):
    return harness.client.get(f"{API_PREFIX}{path}")


def _render_over_http(harness, application_id: str, token: str) -> dict:
    """Submit a render through HTTP and let the real worker run it."""
    response = _post(
        harness,
        f"/applications/{application_id}/document/render",
        {"expected_document_hash": token},
    )
    assert response.status_code == 202, response.text
    assert response.headers["Location"].endswith(response.json()["id"])
    return harness.wait_for_operation(response.json()["id"])


# --- render ------------------------------------------------------------------


def test_a_failed_render_changes_nothing_and_its_retry_is_new_work(
    api_worker, approved_application, deterministic_renderer, monkeypatch
) -> None:
    """§16: a failure records `last_render_error` and touches nothing else.

    The approval, the active files, `rendered_basis` and the hash are compared, not
    one status field. The retry is a new Operation, and only its activation makes the
    document Ready.
    """
    setup = approved_application("Retry Co")
    before = stored_document(setup.services, setup.application_id)

    def explode(*_args, **_kwargs):
        raise OSError("no browser here")

    with monkeypatch.context() as failure_patch:
        failure_patch.setattr("cv_engine.infrastructure.rendering.render_pdf", explode)
        failed = _render_over_http(api_worker, setup.application_id, before.document_hash)
    assert failed["status"] == "failed", failed
    assert failed["failure_code"] in {"RENDER_FAILED", "BROWSER_START_FAILED"}
    after = stored_document(setup.services, setup.application_id)
    assert after.last_render_error is not None
    assert after.last_render_error["document_hash"] == before.document_hash
    for field in (
        "document_hash",
        "approved_basis",
        "approved_at",
        "rendered_basis",
        "html_path",
        "pdf_path",
        "content",
    ):
        assert getattr(after, field) == getattr(before, field), field
    state = _get(api_worker, f"/applications/{setup.application_id}").json()
    assert state["preparation_state"] == "approved"
    assert state["last_render_error"] is not None

    retried = _post(api_worker, f"/operations/{failed['id']}/retry")
    assert retried.status_code == 202, retried.text
    assert retried.json()["id"] != failed["id"]
    assert retried.headers["Location"].endswith(retried.json()["id"])

    completed = api_worker.wait_for_operation(retried.json()["id"])
    assert completed["status"] == "succeeded", completed
    assert completed["retry_of_operation_id"] == failed["id"]
    state = _get(api_worker, f"/applications/{setup.application_id}").json()
    assert state["preparation_state"] == "ready"
    assert state["last_render_error"] is None


def test_render_is_admitted_only_for_an_approved_document(api_worker, drafted_application) -> None:
    """Admission refuses a draft before anything is queued (§16)."""
    setup = drafted_application("Unapproved Render Co")
    response = _post(
        api_worker,
        f"/applications/{setup.application_id}/document/render",
        {"expected_document_hash": setup.document_hash},
    )
    assert response.status_code == 412, response.text
    # Nothing was queued: this Application has run no Operation at all.
    assert (
        _get(api_worker, f"/applications/{setup.application_id}").json()["latest_operation"] is None
    )


# --- the document's files ------------------------------------------------------


def test_the_ready_pdf_is_the_rendered_file_and_nothing_else_is(
    api_worker, ready_application, approved_application
) -> None:
    """`200` with the active PDF while Ready; `412` naming why for anything else."""
    setup = ready_application("Ready Download Co")
    assert setup.pdf is not None
    response = _get(api_worker, f"/applications/{setup.application_id}/document/pdf")

    assert response.status_code == 200, response.text
    assert response.content == setup.pdf.read_bytes()
    assert response.headers["content-type"] == "application/pdf"
    assert int(response.headers["content-length"]) == len(response.content)
    assert response.headers["ETag"] == f'"{setup.document_hash}"'
    assert response.headers["Cache-Control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]

    unrendered = approved_application("Approved Only Co")
    refused = _get(api_worker, f"/applications/{unrendered.application_id}/document/pdf")
    assert refused.status_code == 412, refused.text
    assert refused.json()["code"] == "DOCUMENT_NOT_READY"


def test_the_preview_is_the_current_content_inline_and_safe_to_frame(
    api_worker, document_created, drafted_application
) -> None:
    """Stored nowhere, framed only: the CSP refuses every source but inline style."""
    empty = document_created("Preview Empty Co")
    before_content = _get(api_worker, f"/applications/{empty.application_id}/document/preview")
    assert before_content.status_code == 412, before_content.text

    setup = drafted_application("Preview Co")
    response = _get(api_worker, f"/applications/{setup.application_id}/document/preview")

    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"].startswith("text/html")
    assert response.text.lstrip().lower().startswith("<!doctype html")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "style-src 'unsafe-inline'" in response.headers["Content-Security-Policy"]
    assert "Content-Disposition" not in response.headers
    assert response.headers["ETag"] == f'"{setup.document_hash}"'
    # Nothing was stored: the document is exactly as the draft left it.
    assert stored_document(setup.services, setup.application_id).document_hash == (
        setup.document_hash
    )


def test_decision_markdown_exports_the_documents_provenance(
    api_worker, approved_application
) -> None:
    setup = approved_application("Decision Export Co")

    exported = _get(api_worker, f"/applications/{setup.application_id}/document/decision-markdown")
    unknown = _get(
        api_worker,
        "/applications/00000000-0000-4000-8000-000000000000/document/decision-markdown",
    )

    assert exported.status_code == 200, exported.text
    body = exported.json()
    assert body["application_id"] == setup.application_id
    assert body["document_id"] == stored_document(setup.services, setup.application_id).id
    assert body["markdown"].strip()
    # Nothing in the contract is shaped like a stored location.
    assert set(body) == {"application_id", "document_id", "markdown"}
    assert unknown.status_code == 404, unknown.text


# --- artifact access, by ID and only by ID -----------------------------------
