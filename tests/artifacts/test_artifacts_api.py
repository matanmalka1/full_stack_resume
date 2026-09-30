"""Render, the document's files over HTTP, and artifact access by ID.

Three things here are the point, and the rest is scaffolding around them.

**Nothing addressable is a path.** The artifact routes take an artifact-version ID
and the document routes take the Application's ID, and nothing takes anything else,
so a traversal string is not a special case to defend against - it is an ID that
names no row. These tests send the traversal strings anyway, in several spellings,
and then prove separately that a *registration* pointing outside the project root is
refused - the only way the containment check can be reached, because no client can
address a path to get there.

**A render failure changes nothing about the approval.** The failure lands on the
Operation and on `last_render_error`; the approval stamp, the active files and the
document's hash are read back and compared, not one status string.

**The PDF is answered for what is Ready now.** The document's rendered files are
mutable working outputs, not registered artifacts, so the download checks the basis
when it answers and refuses anything that is not Ready at that moment.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS, analyze_offline
from helpers import ACCOUNT_MANAGER_JOB, artifact_path, stored_document

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import IngestCommand
from cv_engine.infrastructure.persistence.tables import artifact_versions, artifacts
from cv_engine.util import new_id, sha256_bytes, utc_now

#: Several spellings of the same intent, because the layers that could decode
#: them differ: Starlette normalises some, the router decodes others, and a
#: double-encoded one arrives at the handler still looking like a path.
TRAVERSAL_IDS = [
    "../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "....//....//etc/passwd",
]


def _post(harness, path: str, body: dict | None = None, **headers):
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body or {}, headers={**MUTATION_HEADERS, **headers}
    )


def _get(harness, path: str):
    return harness.client.get(f"{API_PREFIX}{path}")


def _artifact(transaction_manager, artifact_catalog, artifact_version_id):
    with transaction_manager.read() as tx:
        return artifact_catalog.artifact_version(tx, artifact_version_id)


def _register(transaction_manager, application_id: str, logical_name: str, path: str) -> str:
    """A provider-response registration holding an arbitrary stored path.

    What a tampered database or a hand-edited row would look like: the only way a
    path can reach the containment check.
    """
    artifact_id, version_id = new_id(), new_id()
    with transaction_manager.write() as tx:
        connection = transaction_manager.connection_for(tx, access="write")
        connection.execute(
            artifacts.insert().values(
                id=artifact_id,
                application_id=application_id,
                artifact_type="provider_response",
                logical_name=logical_name,
                created_at=utc_now(),
            )
        )
        connection.execute(
            artifact_versions.insert().values(
                id=version_id,
                artifact_id=artifact_id,
                version_number=1,
                lifecycle_status="provider-output",
                path=path,
                content_hash="0" * 64,
                created_at=utc_now(),
            )
        )
    return version_id


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


def _provider_responses(harness, company: str) -> tuple[str, list[str]]:
    """An analysed Application and the provider responses its analysis registered."""
    application_id = harness.services.applications.ingest(
        IngestCommand(
            company=company,
            target_role="Account Manager",
            job_text=ACCOUNT_MANAGER_JOB,
            acknowledged_duplicates=True,
            client="web",
        )
    ).application_id
    analyze_offline(harness, application_id, ACCOUNT_MANAGER_JOB)
    listed = _get(harness, f"/applications/{application_id}/artifacts")
    assert listed.status_code == 200, listed.text
    ids = [item["id"] for item in listed.json()["items"]]
    assert ids, "the analysis registered no provider response"
    return application_id, ids


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


def test_a_provider_response_downloads_as_the_bytes_it_registered(
    ai_api_worker, transaction_manager, artifact_catalog
) -> None:
    """The bytes, not just the headers: a `200` with an empty body passed header checks."""
    _, ids = _provider_responses(ai_api_worker, "Evidence Download Co")
    for artifact_version_id in ids:
        response = _get(ai_api_worker, f"/artifacts/{artifact_version_id}/download")
        assert response.status_code == 200, response.text
        stored = artifact_path(
            ai_api_worker.services,
            _artifact(transaction_manager, artifact_catalog, artifact_version_id)["path"],
        )
        assert response.content == stored.read_bytes()
        assert int(response.headers["content-length"]) == len(response.content)
        assert response.headers["ETag"].strip('"') == sha256_bytes(response.content)


def test_artifact_access_is_by_id_and_contained(
    api_worker, document_created, tmp_path, transaction_manager
) -> None:
    """The endpoints take IDs, so traversal has nowhere to be interpreted.

    Whatever each layer does to the spelling, what reaches the handler is an
    identifier. It matches no row, so it is `404`, and the response says nothing
    about the filesystem.

    Containment can then only be reached through a *registration* that holds a path.
    One escaping the root is refused, naming the check rather than the path. So is a
    symlink at a legal location (architecture §14): nothing but resolution can catch
    it, which is why containment resolves before it compares.
    """
    for traversal in TRAVERSAL_IDS:
        for suffix in ("", "/download"):
            response = _get(api_worker, f"/artifacts/{traversal}{suffix}")
            assert response.status_code in {404, 400}, (traversal, suffix, response.text)
            assert "Traceback" not in response.text
            assert "workspace" not in response.text.casefold()

            # An unencoded traversal is resolved by the client before it is sent, so
            # it is answered as whatever unrouted path it collapsed to - still a
            # refusal that reveals nothing, but not a path under `/artifacts`.
            problem = response.json()
            if problem.get("code") == "ROUTE_NOT_FOUND":
                assert problem.get("instance", "").startswith("/api/"), problem
                assert "passwd" not in problem.get("detail", "")
                continue

            assert "/" not in response.text or "artifacts" in problem.get("instance", "")

    setup = document_created("Escape Co")
    escaped_id = _register(
        transaction_manager, setup.application_id, "escaped", "../../../../etc/passwd"
    )
    response = _get(api_worker, f"/artifacts/{escaped_id}/download")
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "ARTIFACT_CONTAINMENT_REFUSED"
    assert "etc/passwd" not in response.text

    outside = tmp_path / "secret.json"
    outside.write_bytes(b'{"secret": true}')
    link_relative = f"artifacts/provider/{setup.application_id}/linked/{'a' * 32}.json"
    link = setup.services.paths.root / link_relative
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    linked_id = _register(transaction_manager, setup.application_id, "linked", link_relative)
    response = _get(api_worker, f"/artifacts/{linked_id}/download")
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "ARTIFACT_CONTAINMENT_REFUSED"
    assert b"secret" not in response.content


def test_an_unregistered_id_is_404_and_a_broken_registration_is_412(
    ai_api_worker, transaction_manager, artifact_catalog
) -> None:
    """Two different findings, two different statuses.

    `404` means the client named nothing. `412` means the client named a record that
    exists and whose stored payload failed verification - tampered, or deleted, which
    is reported as missing rather than as a server error.
    """
    _, ids = _provider_responses(ai_api_worker, "Broken Evidence Co")

    missing = _get(ai_api_worker, "/artifacts/00000000-0000-4000-8000-000000000000/download")
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "UNKNOWN_RECORD"

    tampered_id = ids[0]
    stored = artifact_path(
        ai_api_worker.services,
        _artifact(transaction_manager, artifact_catalog, tampered_id)["path"],
    )
    stored.write_bytes(b'{"tampered": true}')
    tampered = _get(ai_api_worker, f"/artifacts/{tampered_id}/download")
    assert tampered.status_code == 412, tampered.text
    assert tampered.json()["code"] == "ARTIFACT_HASH_MISMATCH"

    body = _get(ai_api_worker, f"/artifacts/{tampered_id}").json()
    assert body["downloadable"] is False
    assert body["unavailable_reason"] == "ARTIFACT_HASH_MISMATCH"
    assert body["size"] is None

    stored.unlink()
    deleted = _get(ai_api_worker, f"/artifacts/{tampered_id}/download")
    assert deleted.status_code == 412, deleted.text
    assert deleted.json()["code"] == "ARTIFACT_PAYLOAD_MISSING"


# --- the verified bytes are the delivered bytes -------------------------------


def test_a_delivery_streams_the_bytes_it_verified_not_the_file_it_reopened(
    ai_api_worker, transaction_manager, artifact_catalog
) -> None:
    """The time-of-check/time-of-use window, closed and proved closed.

    Anything that replaced the payload between verification and streaming would be
    delivered unverified, under the `ETag` and `Content-Length` of the previous
    content. A held descriptor would not close it either: `write_bytes` truncates and
    rewrites the *same inode*, so a held handle reads the substitution. This
    substitutes exactly that way, deliberately.

    Deleting in the same window must not fail after `200` has gone out either.
    """
    services = ai_api_worker.services
    _, ids = _provider_responses(ai_api_worker, "TOCTOU Co")
    record = _artifact(transaction_manager, artifact_catalog, ids[0])
    stored = artifact_path(services, record["path"])
    original = stored.read_bytes()

    delivery = services.rendering.download_artifact(ids[0])

    # The window: verification has happened, not one chunk has been consumed.
    stored.write_bytes(b'{"substituted": true}')

    streamed = b"".join(delivery.stream.chunks())
    assert streamed == original
    assert b"substituted" not in streamed
    assert sha256_bytes(streamed) == record["content_hash"]
    assert delivery.size == len(streamed)
    assert delivery.content_hash == record["content_hash"]

    stored.write_bytes(original)
    delivery = services.rendering.download_artifact(ids[0])
    stored.unlink()

    assert b"".join(delivery.stream.chunks()) == original
