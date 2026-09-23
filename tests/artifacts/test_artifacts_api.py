"""M3 Stage F: render, artifact access by ID, and Ready.

Three things here are the point, and the rest is scaffolding around them.

**Nothing addressable is a path.** Both artifact routes take an
artifact-version ID and there is no third route that takes anything else, so a
traversal string is not a special case to defend against - it is an ID that
names no row. These tests send the traversal strings anyway, in several
spellings, and then prove separately that a *registration* pointing outside the
artifact root is refused - which is the only way the containment check can
actually be reached, because no client can address a path to get there.

**A render failure changes nothing about the approval.** The ApprovedRevision
is immutable; the failure lands on the Operation. The test reads the revision
back and compares the whole record against what it was before the failed
render, rather than asserting that one status string is unchanged.

**Ready is a property of a revision, and separately a property of the active
context.** A new JobSnapshot moves the Application off `ready` while the
revision it moved off stays qualified, exportable, and downloadable. Those are
asserted apart on purpose: stating them together would hide that they are two
different facts.
"""

from __future__ import annotations

from api_harness import MUTATION_HEADERS
from helpers import ACCOUNT_MANAGER_JOB, artifact_path, artifact_reference

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import CreateJobSnapshotCommand
from cv_engine.util import sha256_bytes, sha256_file

#: Several spellings of the same intent, because the layers that could decode
#: them differ: Starlette normalises some, the router decodes others, and a
#: double-encoded one arrives at the handler still looking like a path.
TRAVERSAL_IDS = [
    "../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "....//....//etc/passwd",
]


def _revision(transaction_manager, draft_lifecycle_store, revision_id):
    with transaction_manager.read() as tx:
        return draft_lifecycle_store.approved_revision(tx, revision_id)


def _artifact(transaction_manager, artifact_catalog, artifact_version_id):
    with transaction_manager.read() as tx:
        return artifact_catalog.artifact_version(tx, artifact_version_id)


def _register(transaction_manager, artifact_catalog, *args, **kwargs):
    with transaction_manager.write() as tx:
        return artifact_catalog.register_artifact_version(tx, *args, **kwargs)


def _latest(transaction_manager, artifact_catalog, application_id, artifact_type):
    with transaction_manager.read() as tx:
        return artifact_catalog.latest_artifact_version(tx, application_id, artifact_type)


def _post(harness, path: str, body: dict | None = None, **headers):
    return harness.client.post(
        f"{API_PREFIX}{path}", json=body or {}, headers={**MUTATION_HEADERS, **headers}
    )


def _get(harness, path: str):
    return harness.client.get(f"{API_PREFIX}{path}")


def _render_over_http(harness, application_id: str, revision_id: str, **headers) -> dict:
    """Submit a render through HTTP and let the real worker run it."""
    response = _post(
        harness,
        f"/approved-revisions/{revision_id}/render",
        {"application_id": application_id},
        **headers,
    )
    assert response.status_code == 202, response.text
    assert response.headers["Location"].endswith(response.json()["id"])
    return harness.wait_for_operation(response.json()["id"])


def _rendered(api_worker, artifact_approved_application, company: str = "Render Co"):
    """An Application rendered through the API, with its output IDs.

    `artifact_approved_application` and `api_worker` share the one `services` fixture, so
    the records the first creates are the records the second serves.
    """
    setup = artifact_approved_application(company)
    finished = _render_over_http(api_worker, setup.application_id, setup.approved.revision_id)
    assert finished["status"] == "succeeded", finished
    outputs = {output["output_type"]: output["output_id"] for output in finished["outputs"]}
    return setup, outputs


# --- render ------------------------------------------------------------------


def test_application_lists_its_approved_revisions_with_qualification(
    api_worker,
    artifact_approved_application,
) -> None:
    setup = artifact_approved_application("Revision History Co")

    response = _get(api_worker, f"/applications/{setup.application_id}/approved-revisions")

    assert response.status_code == 200, response.text
    assert [
        (item["id"], item["version_number"], item["ready_qualified"])
        for item in response.json()["items"]
    ] == [(setup.approved.revision_id, 1, False)]


def test_a_failed_render_changes_nothing_and_its_retry_is_new_work(
    api_worker,
    artifact_approved_application,
    deterministic_renderer,
    monkeypatch,
    transaction_manager,
    draft_lifecycle_store,
) -> None:
    """§16 "Render failure leaves ApprovedRevision approved", and §5.4's retry.

    The whole record is compared, not one status field. An ApprovedRevision is
    immutable, so the claim being tested is that *nothing* about it moved - and
    a test that checked one field would still pass if the failure had rewritten
    another. The retry is a new Operation, and only its exact artifacts
    establish Ready.
    """
    setup = artifact_approved_application("Retry Co")
    revision_before = _revision(
        transaction_manager, draft_lifecycle_store, setup.approved.revision_id
    )

    def explode(*_args, **_kwargs):
        raise OSError("no browser here")

    with monkeypatch.context() as failure_patch:
        failure_patch.setattr("cv_engine.infrastructure.rendering.render_pdf", explode)
        failed = _render_over_http(api_worker, setup.application_id, setup.approved.revision_id)
    assert failed["status"] == "failed", failed
    assert failed["failure_code"] in {"RENDER_FAILED", "BROWSER_START_FAILED"}
    assert (
        _revision(transaction_manager, draft_lifecycle_store, setup.approved.revision_id)
        == revision_before
    )
    detail = _get(api_worker, f"/approved-revisions/{setup.approved.revision_id}")
    assert detail.status_code == 200
    assert detail.json()["ready_qualified"] is False

    retried = _post(api_worker, f"/operations/{failed['id']}/retry")
    assert retried.status_code == 202, retried.text
    assert retried.json()["id"] != failed["id"]
    assert retried.headers["Location"].endswith(retried.json()["id"])

    completed = api_worker.wait_for_operation(retried.json()["id"])
    assert completed["status"] == "succeeded", completed
    assert completed["retry_of_operation_id"] == failed["id"]
    assert all(output["active"] for output in completed["outputs"])
    detail = _get(api_worker, f"/applications/{setup.application_id}").json()
    assert detail["preparation_state"] == "ready"
    assert detail["latest_ready_revision_id"] == setup.approved.revision_id


# --- artifact access, by ID and only by ID -----------------------------------


def test_every_rendered_artifact_type_downloads_as_what_it_is(
    api_worker,
    artifact_approved_application,
    deterministic_renderer,
    transaction_manager,
    artifact_catalog,
) -> None:
    """The media type comes from the registered type, never from the filename."""
    setup, outputs = _rendered(api_worker, artifact_approved_application)
    expected = {
        "resume_html": "text/html; charset=utf-8",
        "resume_pdf": "application/pdf",
    }
    for artifact_type, media_type in expected.items():
        artifact_version_id = outputs[artifact_type]
        response = _get(api_worker, f"/artifacts/{artifact_version_id}/download")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == media_type, artifact_type
        # The bytes, not just the headers. A `200` with the right content type
        # and an empty body is exactly what the body-limit middleware produced
        # before `1de0b4f`, and a header-only assertion passed straight through
        # it.
        stored = artifact_path(
            setup.services,
            _artifact(transaction_manager, artifact_catalog, artifact_version_id)["path"],
        )
        assert response.content == stored.read_bytes(), artifact_type
        assert int(response.headers["content-length"]) == len(response.content)


def test_approved_html_preview_streams_only_the_exact_verified_bound_artifact(
    api_worker,
    artifact_approved_application,
    deterministic_renderer,
    transaction_manager,
    artifact_catalog,
) -> None:
    """The preview is the revision's own HTML, inline and safe to frame.

    An artifact from another revision is broken lineage, and the preview
    reuses every artifact-verification failure code: missing, changed, and a
    registration escaping the artifact root.
    """
    setup, outputs = _rendered(api_worker, artifact_approved_application, "Approved Preview Co")
    other, other_outputs = _rendered(
        api_worker, artifact_approved_application, "Preview Other Revision Co"
    )
    html_id = outputs["resume_html"]
    stored = artifact_path(
        setup.services,
        _artifact(transaction_manager, artifact_catalog, html_id)["path"],
    )

    def preview(revision_id: str, artifact_id: str):
        return _get(
            api_worker,
            f"/approved-revisions/{revision_id}/preview?html_artifact_version_id={artifact_id}",
        )

    detail = _get(api_worker, f"/approved-revisions/{setup.approved.revision_id}")
    response = preview(setup.approved.revision_id, html_id)

    assert detail.status_code == 200, detail.text
    assert detail.json()["html_artifact_version_id"] == html_id
    assert response.status_code == 200, response.text
    assert response.content == stored.read_bytes()
    assert response.headers["Content-Type"].startswith("text/html")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "style-src 'unsafe-inline'" in response.headers["Content-Security-Policy"]
    assert "Content-Disposition" not in response.headers
    assert response.headers["ETag"].strip('"') == sha256_bytes(response.content)

    borrowed = preview(setup.approved.revision_id, other_outputs["resume_html"])
    assert borrowed.status_code == 412, borrowed.text
    assert borrowed.json()["code"] == "LINEAGE_BROKEN"
    assert setup.approved.revision_id != other.approved.revision_id

    stored.unlink()
    missing = preview(setup.approved.revision_id, html_id)
    assert missing.status_code == 412, missing.text
    assert missing.json()["code"] == "ARTIFACT_PAYLOAD_MISSING"

    changed_id = other_outputs["resume_html"]
    artifact_path(
        other.services,
        _artifact(transaction_manager, artifact_catalog, changed_id)["path"],
    ).write_bytes(b"<!doctype html><title>tampered</title>")
    changed = preview(other.approved.revision_id, changed_id)
    assert changed.status_code == 412, changed.text
    assert changed.json()["code"] == "ARTIFACT_HASH_MISMATCH"

    escaped_id = _register(
        transaction_manager,
        artifact_catalog,
        setup.application_id,
        "resume_html",
        "escaped-preview",
        "../../../../etc/passwd",
        "0" * 64,
        "rendered",
        revision_id=setup.approved.revision_id,
        job_snapshot_id=setup.snapshot_id,
    )
    escaped = preview(setup.approved.revision_id, escaped_id)
    assert escaped.status_code == 412, escaped.text
    assert escaped.json()["code"] == "ARTIFACT_CONTAINMENT_REFUSED"
    assert "etc/passwd" not in escaped.text


# --- security and failure paths ----------------------------------------------


def test_artifact_access_is_by_id_and_contained(
    api_worker,
    artifact_approved_application,
    tmp_path,
    transaction_manager,
    artifact_catalog,
) -> None:
    """The endpoints take IDs, so traversal has nowhere to be interpreted.

    Whatever each layer does to the spelling, what reaches the handler is an
    identifier. It matches no row, so it is `404`, and the response says nothing
    about the filesystem. `200` would mean a file was served; a `5xx` would mean
    something tried to open it.

    Containment can then only be reached through a *registration* that holds a
    path - what a tampered database or a hand-edited row would look like. One
    escaping the artifact root is refused, naming the check rather than the
    path. So is a symlink at a perfectly legal approved-layout location
    (architecture §14): nothing but resolution can catch it, which is why
    containment resolves before it compares.
    """
    for traversal in TRAVERSAL_IDS:
        for suffix in ("", "/download"):
            response = _get(api_worker, f"/artifacts/{traversal}{suffix}")
            assert response.status_code in {404, 400}, (traversal, suffix, response.text)
            assert "Traceback" not in response.text
            assert "workspace" not in response.text.casefold()

            # An unencoded traversal is resolved by the client before it is sent, so
            # it never reaches this route: it is answered as whatever unrouted path it
            # collapsed to. That is still a refusal that reveals nothing - `instance`
            # is the request path and no more, which is what these assertions check -
            # but it is not a path under `/artifacts`, so the leak check below applies
            # to the ids that do reach the handler.
            problem = response.json()
            if problem.get("code") == "ROUTE_NOT_FOUND":
                assert problem.get("instance", "").startswith("/api/"), problem
                # The refusal names no filesystem location the request did not.
                assert "passwd" not in problem.get("detail", "")
                continue

            assert "/" not in response.text or "artifacts" in problem.get("instance", "")

    setup = artifact_approved_application("Escape Co")
    escaped_id = _register(
        transaction_manager,
        artifact_catalog,
        setup.application_id,
        "resume_pdf",
        "resume",
        "../../../../etc/passwd",
        "0" * 64,
        "rendered",
    )
    response = _get(api_worker, f"/artifacts/{escaped_id}/download")
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "ARTIFACT_CONTAINMENT_REFUSED"
    assert "etc/passwd" not in response.text

    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"%PDF-1.4\nsecret\n")
    link_relative = f"artifacts/outputs/{setup.application_id}/linked/{'a' * 32}.pdf"
    link = setup.services.paths.root / link_relative
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    linked_id = _register(
        transaction_manager,
        artifact_catalog,
        setup.application_id,
        "resume_pdf",
        "linked-resume",
        link_relative,
        "0" * 64,
        "rendered",
    )
    response = _get(api_worker, f"/artifacts/{linked_id}/download")
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "ARTIFACT_CONTAINMENT_REFUSED"
    assert b"secret" not in response.content


def test_an_unregistered_id_is_404_and_a_broken_registration_is_412(
    api_worker,
    artifact_approved_application,
    deterministic_renderer,
    transaction_manager,
    artifact_catalog,
) -> None:
    """Two different findings, two different statuses.

    `404` means the client named nothing. `412` means the client named a record
    that exists and whose stored payload failed verification - tampered, or
    deleted, which is reported as missing rather than as a server error.
    Collapsing them would tell a client that tampered evidence and a typo are
    the same event.
    """
    setup, outputs = _rendered(api_worker, artifact_approved_application)

    missing = _get(api_worker, "/artifacts/00000000-0000-4000-8000-000000000000/download")
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "UNKNOWN_RECORD"

    pdf_id = outputs["resume_pdf"]
    artifact_path(
        setup.services, _artifact(transaction_manager, artifact_catalog, pdf_id)["path"]
    ).write_bytes(b"%PDF-1.4\ntampered\n")
    tampered = _get(api_worker, f"/artifacts/{pdf_id}/download")
    assert tampered.status_code == 412, tampered.text
    assert tampered.json()["code"] == "ARTIFACT_HASH_MISMATCH"

    body = _get(api_worker, f"/artifacts/{pdf_id}").json()
    assert body["downloadable"] is False
    assert body["unavailable_reason"] == "ARTIFACT_HASH_MISMATCH"
    assert body["size"] is None

    html_id = outputs["resume_html"]
    artifact_path(
        setup.services, _artifact(transaction_manager, artifact_catalog, html_id)["path"]
    ).unlink()
    deleted = _get(api_worker, f"/artifacts/{html_id}/download")
    assert deleted.status_code == 412, deleted.text
    assert deleted.json()["code"] == "ARTIFACT_PAYLOAD_MISSING"


# --- Ready -------------------------------------------------------------------


def test_ready_is_the_active_preparation_state_only_while_the_context_matches(
    api_worker, artifact_approved_application, deterministic_renderer
) -> None:
    """§4 rule 2 against §16's last sentence, stated as two separate facts.

    A new JobSnapshot changes the active context. The Application leaves `ready`
    - §4's "old approved/ready milestones remain historical references but do
    not participate in active PreparationState" - while the revision itself is
    untouched: still qualified, still exportable, still downloadable. Both
    halves are asserted because the interesting property is that they differ.
    """
    setup, outputs = _rendered(api_worker, artifact_approved_application, company="Superseded Co")
    revision_id = setup.approved.revision_id

    before = _get(api_worker, f"/applications/{setup.application_id}").json()
    assert before["preparation_state"] == "ready"
    assert before["latest_ready_revision_id"] == revision_id

    setup.services.applications.create_job_snapshot(
        CreateJobSnapshotCommand(
            application_id=setup.application_id,
            job_text=ACCOUNT_MANAGER_JOB + "\n\nUpdated posting: now also owns renewals.",
            client="web",
        )
    )

    after = _get(api_worker, f"/applications/{setup.application_id}").json()
    assert after["preparation_state"] != "ready"
    assert after["preparation_state"] == "needs_analysis"

    revision = _get(api_worker, f"/approved-revisions/{revision_id}").json()
    assert revision["ready_qualified"] is True

    export = _get(
        api_worker,
        f"/approved-revisions/{revision_id}/recruiter-pdf"
        f"?pdf_artifact_version_id={outputs['resume_pdf']}",
    )
    assert export.status_code == 200, export.text
    assert export.content.startswith(b"%PDF")

    download = _get(api_worker, f"/artifacts/{outputs['resume_pdf']}/download")
    assert download.status_code == 200, download.text


# --- the recruiter export ----------------------------------------------------


def test_the_recruiter_export_refuses_a_mixed_pair_and_an_unqualified_revision(
    api_worker,
    artifact_approved_application,
    deterministic_renderer,
    transaction_manager,
    artifact_catalog,
) -> None:
    """Both IDs are checked against each other, and §16 requires `ready_qualified`.

    A PDF from another revision is refused before qualification runs. The
    second refusal reaches the qualification check rather than an earlier one:
    a PDF row is registered against a revision that never rendered, so the type
    check and the revision-binding check both pass and qualification is what
    refuses - there is no rendered HTML, no visual evidence, and no post-render
    validation for this revision. Naming the manifest instead would only have
    proved the type check, a different guard.
    """
    first, first_outputs = _rendered(api_worker, artifact_approved_application, company="Pair A")
    second, _second_outputs = _rendered(api_worker, artifact_approved_application, company="Pair B")

    response = _get(
        api_worker,
        f"/approved-revisions/{second.approved.revision_id}/recruiter-pdf"
        f"?pdf_artifact_version_id={first_outputs['resume_pdf']}",
    )
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "LINEAGE_BROKEN"

    setup = artifact_approved_application("Unrendered Co")
    payload = (
        setup.services.paths.artifacts_root
        / "outputs"
        / setup.application_id
        / setup.approved.revision_id
        / f"{'b' * 32}.pdf"
    )
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(b"%PDF-1.4\nnever rendered\n")

    unrendered_pdf_id = _register(
        transaction_manager,
        artifact_catalog,
        setup.application_id,
        "resume_pdf",
        "resume",
        artifact_reference(setup.services, payload),
        sha256_file(payload),
        "rendered",
        revision_id=setup.approved.revision_id,
    )
    response = _get(
        api_worker,
        f"/approved-revisions/{setup.approved.revision_id}/recruiter-pdf"
        f"?pdf_artifact_version_id={unrendered_pdf_id}",
    )
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "VALIDATION_BLOCKED"
    # The bytes were readable and correctly hashed, so the refusal is the
    # qualification gate rather than a verification failure standing in for it.
    assert b"never rendered" not in response.content


# --- the verified bytes are the delivered bytes -------------------------------


def _rendered_pdf(
    services, artifact_approved_application, transaction_manager, artifact_catalog, company: str
):
    setup = artifact_approved_application(company)
    services.rendering.render(setup.application_id)
    return setup, _latest(transaction_manager, artifact_catalog, setup.application_id, "resume_pdf")


def test_a_delivery_streams_the_bytes_it_verified_not_the_file_it_reopened(
    services,
    artifact_approved_application,
    deterministic_renderer,
    transaction_manager,
    artifact_catalog,
) -> None:
    """The time-of-check/time-of-use window, closed and proved closed.

    `open_artifact` used to verify the path and then hand back a factory that
    reopened it when the response began streaming. Anything that replaced the
    payload in between was delivered unverified, under the `ETag` and
    `Content-Length` taken from the previous content - the client would be told
    it was receiving one document and handed another, with a hash that agreed
    with neither.

    Holding an open descriptor would not have closed it either: `write_bytes`
    truncates and rewrites the *same inode*, so a held handle reads the
    substitution. This substitutes exactly that way, deliberately, because it is
    the case a descriptor-based fix would silently fail.

    Deleting in the same window must not fail after `200` has gone out either:
    the old factory opened the path when streaming began, so an unlink raised
    `FileNotFoundError` from inside the response body, after the status line
    and headers were already on the wire.
    """
    setup, pdf = _rendered_pdf(
        services,
        artifact_approved_application,
        transaction_manager,
        artifact_catalog,
        "TOCTOU Co",
    )
    stored = artifact_path(services, pdf["path"])
    original = stored.read_bytes()

    delivery = services.rendering.download_artifact(pdf["id"])

    # The window: verification has happened, not one chunk has been consumed.
    stored.write_bytes(b"%PDF-1.4\nsubstituted payload\n")

    streamed = b"".join(delivery.stream.chunks())
    assert streamed == original
    assert b"substituted" not in streamed
    assert sha256_bytes(streamed) == pdf["content_hash"]
    # The headers a router derives describe the bytes that were actually sent.
    assert delivery.size == len(streamed)
    assert delivery.content_hash == pdf["content_hash"]

    stored.write_bytes(original)
    delivery = services.rendering.download_artifact(pdf["id"])
    stored.unlink()

    assert b"".join(delivery.stream.chunks()) == original


def test_decision_markdown_exports_provenance_and_refuses_another_application(
    api_worker, artifact_approved_application
) -> None:
    """The human-readable provenance record, bound to the Application that owns it."""
    setup = artifact_approved_application("Decision Export Co")
    other = artifact_approved_application("Other Decision Co")
    revision_id = setup.approved.revision_id

    exported = _get(
        api_worker,
        f"/approved-revisions/{revision_id}/decision-markdown"
        f"?application_id={setup.application_id}",
    )
    mismatched = _get(
        api_worker,
        f"/approved-revisions/{revision_id}/decision-markdown"
        f"?application_id={other.application_id}",
    )

    assert exported.status_code == 200, exported.text
    body = exported.json()
    assert body["approved_revision_id"] == revision_id
    assert body["application_id"] == setup.application_id
    assert body["content"].strip()
    assert body["content_hash"]
    # The save name is transport, not a body field: nothing in the contract is
    # shaped like a stored location.
    assert "filename" not in body
    assert "attachment" in exported.headers["Content-Disposition"]

    assert mismatched.status_code == 409, mismatched.text
