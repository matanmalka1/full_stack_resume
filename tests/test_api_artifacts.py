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

import json

import pytest
from api_harness import MUTATION_HEADERS
from helpers import ACCOUNT_MANAGER_JOB

from cv_engine.api.app import API_PREFIX
from cv_engine.application.commands import CreateJobSnapshotCommand
from cv_engine.application.errors import (
    ArtifactContainmentRefused,
    ArtifactHashMismatch,
    ArtifactPayloadMissing,
    UnknownRecord,
)
from cv_engine.util import sha256_file

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


def _rendered(api_worker, approved_application, company: str = "Render Co"):
    """An Application rendered through the API, with its output IDs.

    `approved_application` and `api_worker` share the one `services` fixture, so
    the records the first creates are the records the second serves.
    """
    setup = approved_application(company)
    finished = _render_over_http(api_worker, setup.application_id, setup.approved.revision_id)
    assert finished["status"] == "succeeded", finished
    outputs = {output["output_type"]: output["output_id"] for output in finished["outputs"]}
    return setup, outputs


# --- render ------------------------------------------------------------------


def test_render_is_accepted_as_an_operation_and_registers_three_artifacts(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """§16 through §21/§22: `202`, a `Location`, and the three rendered outputs."""
    setup, outputs = _rendered(api_worker, approved_application)
    assert set(outputs) == {"resume_html", "resume_pdf", "visual_evidence"}

    detail = _get(api_worker, f"/approved-revisions/{setup.approved.revision_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["ready_qualified"] is True
    assert body["pdf_artifact_version_id"] == outputs["resume_pdf"]


def test_render_addressed_to_the_wrong_application_is_refused_before_queueing(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """The body states which Application the client believes it is rendering for.

    A mismatch is `412 LINEAGE_BROKEN` and no Operation is created, so a render
    cannot land on another Application's revision because two IDs were confused.
    """
    setup = approved_application("Lineage Co")
    other = approved_application("Other Co")
    before = len(setup.services.repository.artifact_versions(setup.application_id))

    response = _post(
        api_worker,
        f"/approved-revisions/{setup.approved.revision_id}/render",
        {"application_id": other.application_id},
    )
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "LINEAGE_BROKEN"
    assert len(setup.services.repository.artifact_versions(setup.application_id)) == before


def test_an_idempotency_key_returns_the_first_render_instead_of_a_second(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """§21: the same key with the same payload does not queue a second render."""
    setup = approved_application("Idempotent Co")
    headers = {"Idempotency-Key": "render-once"}
    first = _post(
        api_worker,
        f"/approved-revisions/{setup.approved.revision_id}/render",
        {"application_id": setup.application_id},
        **headers,
    )
    second = _post(
        api_worker,
        f"/approved-revisions/{setup.approved.revision_id}/render",
        {"application_id": setup.application_id},
        **headers,
    )
    assert first.status_code == 202 and second.status_code == 202, second.text
    assert first.json()["id"] == second.json()["id"]


def test_a_failed_render_leaves_the_approved_revision_exactly_as_it_was(
    api_worker, approved_application, monkeypatch
) -> None:
    """§16: "Render failure leaves ApprovedRevision approved."

    The whole record is compared, not one status field. An ApprovedRevision is
    immutable, so the claim being tested is that *nothing* about it moved - and
    a test that checked one field would still pass if the failure had rewritten
    another.
    """
    setup = approved_application("Failing Co")

    def explode(*_args, **_kwargs):
        raise OSError("no browser here")

    monkeypatch.setattr("cv_engine.infrastructure.rendering.render_pdf", explode)

    before = setup.services.repository.approved_revision(setup.approved.revision_id)
    finished = _render_over_http(api_worker, setup.application_id, setup.approved.revision_id)

    assert finished["status"] == "failed", finished
    assert finished["failure_code"] in {"RENDER_FAILED", "BROWSER_START_FAILED"}
    after = setup.services.repository.approved_revision(setup.approved.revision_id)
    assert after == before

    detail = _get(api_worker, f"/approved-revisions/{setup.approved.revision_id}")
    assert detail.status_code == 200
    assert detail.json()["ready_qualified"] is False


def test_retrying_a_failed_render_creates_a_new_operation(
    api_worker, approved_application, monkeypatch
) -> None:
    """§16: "Retry creates a new Operation" - not a reopening of the failed one."""
    setup = approved_application("Retry Co")

    def explode(*_args, **_kwargs):
        raise OSError("no browser here")

    monkeypatch.setattr("cv_engine.infrastructure.rendering.render_pdf", explode)
    failed = _render_over_http(api_worker, setup.application_id, setup.approved.revision_id)
    assert failed["status"] == "failed", failed

    retried = _post(api_worker, f"/operations/{failed['id']}/retry")
    assert retried.status_code == 202, retried.text
    assert retried.json()["id"] != failed["id"]
    assert retried.headers["Location"].endswith(retried.json()["id"])


# --- artifact access, by ID and only by ID -----------------------------------


def test_metadata_and_download_are_reached_by_artifact_version_id(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """§21: `GET /artifacts/{id}` and `/download`, with no path anywhere."""
    _setup, outputs = _rendered(api_worker, approved_application)
    pdf_id = outputs["resume_pdf"]

    metadata = _get(api_worker, f"/artifacts/{pdf_id}")
    assert metadata.status_code == 200, metadata.text
    body = metadata.json()
    assert body["id"] == pdf_id
    assert body["artifact_type"] == "resume_pdf"
    assert body["downloadable"] is True
    assert body["unavailable_reason"] is None
    assert body["size"] > 0

    download = _get(api_worker, f"/artifacts/{pdf_id}/download")
    assert download.status_code == 200, download.text
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")
    assert int(download.headers["content-length"]) == len(download.content)
    assert download.headers["etag"].strip('"') == body["content_hash"]


def test_the_metadata_response_carries_no_stored_location(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """§20: "They return DTOs, not database rows or local paths."

    Compared against the response model's own field set rather than a
    hand-written list. A list would be written from the same belief that the
    projection is narrow, which is exactly the belief that was wrong three times
    in M3 - so the assertion has to come from the schema.
    """
    from cv_engine.api.schemas.artifacts import ArtifactVersionDetailResponse

    _setup, outputs = _rendered(api_worker, approved_application)
    body = _get(api_worker, f"/artifacts/{outputs['resume_pdf']}").json()
    assert set(body) == set(ArtifactVersionDetailResponse.model_fields)
    assert "path" not in body


def test_the_pdf_downloads_under_its_registered_recruiter_filename(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """Architecture §6.2: a recruiter name is a delivery name, not an identity.

    The name in the header is the one render recorded in the artifact's own
    metadata, and the stored file is still the UUID. Both halves are asserted:
    a test that only checked the header would pass if the physical file had been
    renamed to match.
    """
    setup, outputs = _rendered(api_worker, approved_application)
    pdf_id = outputs["resume_pdf"]
    registered = setup.services.repository.artifact_version(pdf_id)

    download = _get(api_worker, f"/artifacts/{pdf_id}/download")
    disposition = download.headers["content-disposition"]
    assert disposition.startswith("attachment; ")
    assert "CV.pdf" in disposition
    assert pdf_id in registered["path"]
    assert "CV.pdf" not in registered["path"]


def test_every_rendered_artifact_type_downloads_as_what_it_is(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """The media type comes from the registered type, never from the filename."""
    _setup, outputs = _rendered(api_worker, approved_application)
    expected = {
        "resume_html": "text/html; charset=utf-8",
        "resume_pdf": "application/pdf",
        "visual_evidence": "image/png",
    }
    for artifact_type, media_type in expected.items():
        response = _get(api_worker, f"/artifacts/{outputs[artifact_type]}/download")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == media_type, artifact_type


def test_the_approved_markdown_and_manifest_download_without_a_render(
    api_worker, approved_application
) -> None:
    """Download does not require Ready qualification, and says so by working.

    Approval registers the Markdown and the claim manifest before any render
    exists. They are registered artifacts, so they are downloadable; only the
    recruiter export requires qualification.
    """
    setup = approved_application("Pre-render Co")
    for artifact_version_id in (
        setup.approved.markdown_artifact_version_id,
        setup.approved.manifest_artifact_version_id,
    ):
        response = _get(api_worker, f"/artifacts/{artifact_version_id}/download")
        assert response.status_code == 200, response.text
        assert response.content


# --- security and failure paths ----------------------------------------------


@pytest.mark.parametrize("traversal", TRAVERSAL_IDS)
def test_a_traversal_string_is_only_an_id_that_names_nothing(
    api_worker, approved_application, traversal
) -> None:
    """The endpoints take IDs, so traversal has nowhere to be interpreted.

    Whatever each layer does to the spelling, what reaches the handler is an
    identifier. It matches no row, so it is `404`, and the response says nothing
    about the filesystem. `200` would mean a file was served; a `5xx` would mean
    something tried to open it.
    """
    for suffix in ("", "/download"):
        response = _get(api_worker, f"/artifacts/{traversal}{suffix}")
        assert response.status_code in {404, 400}, (traversal, suffix, response.text)
        assert "/" not in response.text or "artifacts" in response.json().get("instance", "")
        assert "Traceback" not in response.text
        assert "workspace" not in response.text.casefold()


def test_an_unregistered_id_is_404_and_a_broken_registration_is_412(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """Two different findings, two different statuses.

    `404` means the client named nothing. `412` means the client named a record
    that exists and whose stored payload failed verification. Collapsing them
    would tell a client that tampered evidence and a typo are the same event.
    """
    setup, outputs = _rendered(api_worker, approved_application)

    missing = _get(api_worker, "/artifacts/00000000-0000-4000-8000-000000000000/download")
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "UNKNOWN_RECORD"

    pdf_id = outputs["resume_pdf"]
    setup.services.artifacts.resolve(
        setup.services.repository.artifact_version(pdf_id)["path"]
    ).write_bytes(b"%PDF-1.4\ntampered\n")
    tampered = _get(api_worker, f"/artifacts/{pdf_id}/download")
    assert tampered.status_code == 412, tampered.text
    assert tampered.json()["code"] == "ARTIFACT_HASH_MISMATCH"


def test_a_hash_mismatch_also_makes_the_metadata_say_it_is_not_downloadable(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """The eligibility answer and the download answer cannot disagree.

    They run the same verification, so a client that asked first is not
    surprised second.
    """
    setup, outputs = _rendered(api_worker, approved_application)
    pdf_id = outputs["resume_pdf"]
    setup.services.artifacts.resolve(
        setup.services.repository.artifact_version(pdf_id)["path"]
    ).write_bytes(b"%PDF-1.4\ntampered\n")

    body = _get(api_worker, f"/artifacts/{pdf_id}").json()
    assert body["downloadable"] is False
    assert body["unavailable_reason"] == "ARTIFACT_HASH_MISMATCH"
    assert body["size"] is None


def test_a_deleted_payload_is_reported_as_missing_rather_than_as_a_server_error(
    api_worker, approved_application, deterministic_renderer
) -> None:
    setup, outputs = _rendered(api_worker, approved_application)
    pdf_id = outputs["resume_pdf"]
    setup.services.artifacts.resolve(
        setup.services.repository.artifact_version(pdf_id)["path"]
    ).unlink()

    response = _get(api_worker, f"/artifacts/{pdf_id}/download")
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "ARTIFACT_PAYLOAD_MISSING"


def test_a_registration_pointing_outside_the_artifact_root_is_refused(
    api_worker, approved_application
) -> None:
    """The containment check, reached the only way a client could reach it.

    No endpoint accepts a path, so containment can only be exercised through a
    *registration* that holds one. This registers a row whose path escapes the
    artifact root, which is what a tampered database or a hand-edited row would
    look like, and asserts the refusal names the check rather than the path.
    """
    setup = approved_application("Escape Co")
    escaped_id = setup.services.repository.register_artifact_version(
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


def test_a_symlink_out_of_the_artifact_root_is_refused_by_the_same_check(
    api_worker, approved_application, tmp_path
) -> None:
    """Architecture §14: "Artifact access prevents traversal and symlink escape."

    The link sits at a perfectly legal approved-layout location, so nothing but
    resolution can catch it - which is the reason containment resolves before it
    compares instead of checking the unresolved string.
    """
    setup = approved_application("Symlink Co")
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"%PDF-1.4\nsecret\n")

    link_relative = f"artifacts/outputs/{setup.application_id}/linked/{'a' * 32}.pdf"
    link = setup.services.workspace.root / link_relative
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    linked_id = setup.services.repository.register_artifact_version(
        setup.application_id,
        "resume_pdf",
        "resume",
        link_relative,
        "0" * 64,
        "rendered",
    )
    response = _get(api_worker, f"/artifacts/{linked_id}/download")
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "ARTIFACT_CONTAINMENT_REFUSED"
    assert b"secret" not in response.content


def test_no_artifact_refusal_leaks_a_path_a_trace_or_the_workspace(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """§22: Problem Details carries a stable code and safe context, and no more.

    Checked over every refusal this stage can produce, in one place, so a new
    refusal that leaked would have to be added here to be believed safe.
    """
    setup, outputs = _rendered(api_worker, approved_application)
    workspace_root = str(setup.services.workspace.root)
    pdf_id = outputs["resume_pdf"]
    setup.services.artifacts.resolve(
        setup.services.repository.artifact_version(pdf_id)["path"]
    ).write_bytes(b"tampered")

    responses = [
        _get(api_worker, "/artifacts/not-an-id"),
        _get(api_worker, "/artifacts/not-an-id/download"),
        _get(api_worker, f"/artifacts/{pdf_id}/download"),
        _get(api_worker, "/approved-revisions/not-an-id"),
        _get(api_worker, f"/approved-revisions/{setup.approved.revision_id}/recruiter-pdf"),
    ]
    for response in responses:
        assert response.status_code >= 400, response.text
        text = response.text
        assert workspace_root not in text
        assert "Traceback" not in text
        assert "artifacts/outputs" not in text
        assert "/Users/" not in text


# --- Ready -------------------------------------------------------------------


def test_ready_qualification_is_exposed_and_not_recomputed_by_the_router(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """The endpoint reports what the application layer derived, exactly.

    Asserted by comparing the response against a direct call to the service, so
    "the router does not recompute Ready" is measured rather than promised. If a
    router ever grew its own rule, these two would drift and this would fail.
    """
    setup, _outputs = _rendered(api_worker, approved_application)
    revision_id = setup.approved.revision_id

    from_service = setup.services.rendering.revision_ready_qualification(revision_id)
    from_http = _get(api_worker, f"/approved-revisions/{revision_id}").json()

    assert from_http["ready_qualified"] is from_service.ready_qualified
    assert from_http["pdf_artifact_version_id"] == from_service.pdf_artifact_version_id
    assert from_http["ready_validation"] == from_service.validation.model_dump(mode="json")


def test_ready_is_the_active_preparation_state_only_while_the_context_matches(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """§4 rule 2 against §16's last sentence, stated as two separate facts.

    A new JobSnapshot changes the active context. The Application leaves `ready`
    - §4's "old approved/ready milestones remain historical references but do
    not participate in active PreparationState" - while the revision itself is
    untouched: still qualified, still exportable, still downloadable. Both
    halves are asserted because the interesting property is that they differ.
    """
    setup, outputs = _rendered(api_worker, approved_application, company="Superseded Co")
    revision_id = setup.approved.revision_id

    before = _get(api_worker, f"/applications/{setup.application_id}").json()
    assert before["preparation_state"] == "ready"
    assert before["latest_ready_revision_id"] == revision_id

    setup.services.applications.create_job_snapshot(
        CreateJobSnapshotCommand(
            application_id=setup.application_id,
            job_text=ACCOUNT_MANAGER_JOB + "\n\nUpdated posting: now also owns renewals.",
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


def test_the_recruiter_export_needs_both_ids_and_uses_the_registered_name(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """§16: registration, binding, and qualification, then the friendly name."""
    setup, outputs = _rendered(api_worker, approved_application)
    revision_id = setup.approved.revision_id
    pdf_id = outputs["resume_pdf"]

    response = _get(
        api_worker,
        f"/approved-revisions/{revision_id}/recruiter-pdf?pdf_artifact_version_id={pdf_id}",
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"

    registered = setup.services.repository.artifact_version(pdf_id)
    expected = json.loads(registered["metadata_json"])["recruiter_filename"]
    assert expected in response.headers["content-disposition"]


def test_the_recruiter_export_requires_the_pdf_artifact_version_id(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """No `latest`. The exact PDF is named or the request is invalid (§12)."""
    setup, _outputs = _rendered(api_worker, approved_application)
    response = _get(api_worker, f"/approved-revisions/{setup.approved.revision_id}/recruiter-pdf")
    assert response.status_code == 422, response.text


def test_a_pdf_from_another_revision_is_refused_before_qualification_runs(
    api_worker, approved_application, deterministic_renderer
) -> None:
    """Both IDs are checked against each other, so the pair cannot be mixed."""
    first, first_outputs = _rendered(api_worker, approved_application, company="Pair A")
    second, _second_outputs = _rendered(api_worker, approved_application, company="Pair B")

    response = _get(
        api_worker,
        f"/approved-revisions/{second.approved.revision_id}/recruiter-pdf"
        f"?pdf_artifact_version_id={first_outputs['resume_pdf']}",
    )
    assert response.status_code == 412, response.text
    assert response.json()["code"] == "LINEAGE_BROKEN"


def test_an_unqualified_revision_refuses_its_export(api_worker, approved_application) -> None:
    """§16 requires `ready_qualified`, and this reaches that check rather than an earlier one.

    A PDF row is registered against a revision that never rendered, so the type
    check and the revision-binding check both pass and qualification is what
    refuses: there is no rendered HTML, no visual evidence, and no post-render
    validation for this revision. Naming the manifest instead would have been
    easier and would only have proved the type check, which is a different
    guard - the test would have passed while the qualification gate was absent.
    """
    setup = approved_application("Unrendered Co")
    payload = (
        setup.services.workspace.artifacts_root
        / "outputs"
        / setup.application_id
        / setup.approved.revision_id
        / f"{'b' * 32}.pdf"
    )
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(b"%PDF-1.4\nnever rendered\n")

    unrendered_pdf_id = setup.services.repository.register_artifact_version(
        setup.application_id,
        "resume_pdf",
        "resume",
        setup.services.artifacts.relative(payload),
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


# --- the application-layer refusals, named ------------------------------------


def test_the_three_artifact_refusals_are_distinguishable_at_the_application_layer(
    services, approved_application, deterministic_renderer, tmp_path
) -> None:
    """Each check fails as its own class, so a caller can tell them apart.

    Without this the three would only be distinguishable by message, and a
    message is the one part of a refusal that is free to be rewritten.
    """
    setup = approved_application("Taxonomy Co")
    services.rendering.render(setup.application_id)
    pdf = services.repository.latest_artifact_version(setup.application_id, "resume_pdf")

    with pytest.raises(UnknownRecord):
        services.rendering.download_artifact("no-such-artifact")

    services.artifacts.resolve(pdf["path"]).write_bytes(b"changed")
    with pytest.raises(ArtifactHashMismatch):
        services.rendering.download_artifact(pdf["id"])

    services.artifacts.resolve(pdf["path"]).unlink()
    with pytest.raises(ArtifactPayloadMissing):
        services.rendering.download_artifact(pdf["id"])

    escaped = services.repository.register_artifact_version(
        setup.application_id, "resume_pdf", "resume", "../outside.pdf", "0" * 64, "rendered"
    )
    with pytest.raises(ArtifactContainmentRefused):
        services.rendering.download_artifact(escaped)
