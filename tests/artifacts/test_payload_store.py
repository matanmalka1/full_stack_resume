from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from cv_engine.application.errors import ArtifactPayloadMissing
from cv_engine.application.ports.documents import RenderedFiles
from cv_engine.infrastructure.document_files import DocumentFiles
from cv_engine.infrastructure.payloads import PayloadStore
from cv_engine.runtime.paths import AppPaths


@pytest.fixture
def payload_store(tmp_path: Path) -> PayloadStore:
    root = tmp_path / "project"
    root.mkdir()
    return PayloadStore(AppPaths.from_root(root))


def test_immutable_payload_families_include_submissions(payload_store: PayloadStore):
    destinations = [
        payload_store.snapshot_path("app", "snapshot"),
        *(
            payload_store.submission_path("app", "submission", suffix=suffix)
            for suffix in ("html", "pdf")
        ),
    ]
    for index, destination in enumerate(destinations):
        payload = f"payload-{index}".encode()
        stored = payload_store.commit(
            destination, payload=payload, validate=lambda value: bool(value)
        )
        assert destination.read_bytes() == payload
        assert stored.sha256 == hashlib.sha256(payload).hexdigest()
        assert payload_store.verify_payload(stored.project_relative, stored.sha256) == "ok"
        with pytest.raises(FileExistsError):
            payload_store.commit(destination, payload=b"replacement", validate=lambda _value: True)


def test_commit_validates_before_storing_and_keys_each_attempt_immutably(
    payload_store: PayloadStore,
) -> None:
    content = b"exact snapshot text\n"
    destination = payload_store.snapshot_path("app", "snapshot")
    observed: list[bytes] = []

    def validate(payload: bytes) -> None:
        # Validation sees the exact bytes, and runs before the key is claimed:
        # a payload that fails it must never occupy its destination. That is
        # what the deleted temp file used to buy, without the temp file.
        observed.append(payload)
        assert not destination.exists()

    stored = payload_store.commit(destination, payload=content, validate=validate)

    assert observed == [content]
    assert stored.project_relative == "artifacts/snapshots/app/snapshot.txt"
    assert stored.sha256 == hashlib.sha256(content).hexdigest()
    assert stored.size == len(content)
    assert destination.read_bytes() == content

    first = payload_store.commit_submission_file(
        "app", "submission-1", suffix="pdf", payload=b"first"
    )
    second = payload_store.commit_submission_file(
        "app", "submission-2", suffix="pdf", payload=b"first"
    )
    assert first.reference != second.reference
    with pytest.raises(FileExistsError, match="immutable payload already exists"):
        payload_store.commit_submission_file(
            "app", "submission-1", suffix="pdf", payload=b"changed"
        )


def test_traversal_symlink_and_unapproved_destinations_are_refused(
    payload_store: PayloadStore, tmp_path: Path
) -> None:
    assert (
        payload_store.verify_payload("artifacts/outputs/app/revision/retired.png", "0" * 64)
        == "unresolvable"
    )
    with pytest.raises(ValueError, match="invalid application_id path component"):
        payload_store.snapshot_path("../outside", "snapshot")
    with pytest.raises(ValueError, match="contains traversal"):
        payload_store.commit(
            "snapshots/app/../outside/snapshot.txt",
            payload=b"no",
            validate=lambda _payload: True,
        )
    with pytest.raises(ValueError, match="contains traversal"):
        payload_store.commit(
            tmp_path
            / "project"
            / "artifacts"
            / "snapshots"
            / "app"
            / ".."
            / "outside"
            / "snapshot.txt",
            payload=b"no",
            validate=lambda _payload: True,
        )
    with pytest.raises(ValueError, match="not an approved layout"):
        payload_store.commit(
            "working/app/resume.md",
            payload=b"no",
            validate=lambda _payload: True,
        )
    # Retired layouts stay refused: architecture §6.2 approves only JobSnapshots
    # and Submission files.
    for retired in (
        "revisions/app/rev/attempt/resume.json",
        "outputs/app/rev/id.pdf",
        "drafts/app/draft-v1.json",
        f"manifests/{uuid4()}.json",
    ):
        with pytest.raises(ValueError, match="not an approved layout"):
            payload_store.commit(retired, payload=b"{}", validate=lambda _payload: True)

    artifacts = tmp_path / "project" / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "snapshots").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="path escapes configured root"):
        payload_store.snapshot_path("app", "snapshot")

    assert list(outside.iterdir()) == []


def test_failed_validation_never_claims_the_destination_key(
    payload_store: PayloadStore,
) -> None:
    """What replaced the temp-orphan test.

    Temp staging existed so a payload that failed validation could not appear
    at its destination, and `temp_orphans` reported what staging left behind.
    Direct PUT removes the staging and therefore the orphan: validation now
    runs on the bytes before the key is claimed. The property worth asserting
    is the one that always mattered - a rejected payload is not stored - not
    the leftover file that the old mechanism happened to produce.
    """
    destination = payload_store.snapshot_path("app", "snapshot")

    with pytest.raises(ValueError, match="payload validation failed"):
        payload_store.commit(
            destination,
            payload=b"invalid",
            validate=lambda _payload: False,
        )

    assert not destination.exists()
    # The key is free, so the same destination still accepts a valid payload.
    stored = payload_store.commit(
        destination,
        payload=b"valid",
        validate=lambda _payload: True,
    )
    assert destination.read_bytes() == b"valid"
    assert stored.project_relative == "artifacts/snapshots/app/snapshot.txt"


def test_document_attempts_are_unique_and_submission_copies_are_managed(tmp_path):
    root = tmp_path / "documents"
    root.mkdir()
    paths = AppPaths.from_root(root)
    payloads = PayloadStore(paths)
    files = DocumentFiles(paths, payloads)
    html, pdf = files.render_targets("app", "attempt")
    html.write_bytes(b"<html>CV</html>")
    pdf.write_bytes(b"%PDF-CV")
    with pytest.raises(FileExistsError):
        files.render_targets("app", "attempt")
    references = RenderedFiles(html=files.reference_for(html), pdf=files.reference_for(pdf))
    sent = files.copy_for_submission("app", "submission", references)
    assert sent.html_path == "artifacts/submissions/app/submission/resume.html"
    assert sent.pdf_path == "artifacts/submissions/app/submission/resume.pdf"
    assert payloads.verify_payload(sent.html_path, sent.html_sha256) == "ok"
    assert payloads.verify_payload(sent.pdf_path, sent.pdf_sha256) == "ok"
    assert b"".join(files.open_rendered_pdf(references.pdf).chunks()) == b"%PDF-CV"
    files.discard(references)
    assert not html.exists() and not pdf.exists()
    assert payloads.verify_payload(sent.pdf_path, sent.pdf_sha256) == "ok"
    with pytest.raises(ArtifactPayloadMissing):
        files.open_rendered_pdf(references.pdf)
