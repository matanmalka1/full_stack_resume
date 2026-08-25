from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from cv_engine.application.errors import ArtifactPayloadMissing
from cv_engine.infrastructure.payloads import PayloadStore


@pytest.fixture
def payload_store(tmp_path: Path) -> PayloadStore:
    root = tmp_path / "project"
    paths = SimpleNamespace(
        root=root,
        artifacts_root=root / "artifacts",
        temp_root=root / "tmp",
    )
    return PayloadStore(paths)


def test_approved_payload_layouts(payload_store: PayloadStore) -> None:
    manifest_id = str(uuid.uuid4())

    assert payload_store.snapshot_path("app", "snapshot").parts[-3:] == (
        "snapshots",
        "app",
        "snapshot.txt",
    )
    assert payload_store.revision_path("app", "revision", format="json").parts[-4:] == (
        "revisions",
        "app",
        "revision",
        "resume.json",
    )
    assert payload_store.revision_path("app", "revision", format="md").name == "resume.md"
    for suffix in ("html", ".pdf", "png"):
        assert (
            payload_store.output_path("app", "revision", "artifact", suffix=suffix).suffix
            == f".{suffix.lstrip('.')}"
        )
    targets = payload_store.render_targets(
        "app", "revision", "html-id", "pdf-id", "screenshot-id", "Recruiter CV.pdf"
    )
    assert targets.html.parts[-4:] == ("outputs", "app", "revision", "html-id.html")
    assert targets.pdf.name == "pdf-id.pdf"
    assert targets.screenshot.name == "screenshot-id.png"
    assert targets.recruiter_pdf_filename == "Recruiter CV.pdf"
    assert payload_store.provider_path("app", "operation", "artifact").parts[-4:] == (
        "provider",
        "app",
        "operation",
        "artifact.json",
    )
    assert payload_store.manifest_path(manifest_id).parts[-2:] == (
        "manifests",
        f"{manifest_id}.json",
    )

    with pytest.raises(ValueError, match="UUIDv4"):
        payload_store.manifest_path("manifest-latest")
    with pytest.raises(ValueError, match="UUIDv4"):
        payload_store.manifest_path(str(uuid.uuid1()))


def test_commit_validates_before_storing_and_returns_registration_metadata(
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
    assert stored.path == destination
    assert stored.project_relative == "artifacts/snapshots/app/snapshot.txt"
    assert stored.sha256 == hashlib.sha256(content).hexdigest()
    assert stored.size == len(content)
    assert destination.read_bytes() == content


def test_commit_supports_every_approved_payload_family(payload_store: PayloadStore) -> None:
    destinations = [
        payload_store.revision_path("app", "revision", format="json"),
        payload_store.revision_path("app", "revision", format="md"),
        payload_store.output_path("app", "revision", "html", suffix="html"),
        payload_store.output_path("app", "revision", "pdf", suffix="pdf"),
        payload_store.output_path("app", "revision", "png", suffix="png"),
        payload_store.provider_path("app", "operation", "response"),
        payload_store.manifest_path(str(uuid.uuid4())),
    ]

    for number, destination in enumerate(destinations):
        content = f"payload-{number}".encode()
        stored = payload_store.commit(
            destination,
            payload=content,
            validate=lambda _payload: True,
        )
        assert stored.path.read_bytes() == content


def test_existing_immutable_payload_is_never_overwritten(
    payload_store: PayloadStore,
) -> None:
    destination = payload_store.snapshot_path("app", "snapshot")
    payload_store.commit(
        destination,
        payload=b"original",
        validate=lambda _payload: True,
    )

    with pytest.raises(FileExistsError, match="immutable payload already exists"):
        payload_store.commit(
            destination,
            payload=b"replacement",
            validate=lambda _payload: True,
        )
    assert destination.read_bytes() == b"original"


def test_revision_commit_reuses_only_exact_recovery_orphans(payload_store: PayloadStore) -> None:
    first = payload_store.commit_revision("app", "revision", '{"value":1}', "markdown")
    recovered = payload_store.commit_revision("app", "revision", '{"value":1}', "markdown")
    assert recovered == first

    with pytest.raises(FileExistsError, match="different content"):
        payload_store.commit_revision("app", "revision", '{"value":2}', "markdown")


def test_traversal_and_unapproved_destinations_are_refused(
    payload_store: PayloadStore, tmp_path: Path
) -> None:
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
    with pytest.raises(ValueError, match="UUIDv4"):
        payload_store.commit(
            "manifests/latest.json",
            payload=b"no",
            validate=lambda _payload: True,
        )


def test_symlink_escapes_are_refused_before_a_write(
    payload_store: PayloadStore, tmp_path: Path
) -> None:
    artifacts = tmp_path / "project" / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts.mkdir(parents=True)
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


def test_ingest_render_output_matches_the_reference_the_registry_records(
    payload_store: PayloadStore,
) -> None:
    """Rendered outputs are the one family that arrives as a file, not bytes.

    Chromium writes them to the paths `render_targets` hands it, so they enter
    storage by location. What must not move is the stored reference: an
    `artifact_versions` row records this string, and it has to be exactly what
    the previous `ArtifactStore.relative(path)` produced.
    """
    targets = payload_store.render_targets(
        "app", "revision", "html-id", "pdf-id", "screenshot-id", "Recruiter CV.pdf"
    )
    content = b"<html>rendered</html>"
    targets.html.parent.mkdir(parents=True, exist_ok=True)
    targets.html.write_bytes(content)

    stored = payload_store.ingest_render_output(targets.html)

    assert stored.reference == "artifacts/outputs/app/revision/html-id.html"
    assert stored.sha256 == hashlib.sha256(content).hexdigest()
    assert stored.size == len(content)
    # Served back through the same path a download takes.
    stream = payload_store.open_artifact(stored.reference, stored.sha256)
    assert b"".join(stream.chunks()) == content


def test_ingest_render_output_refuses_a_file_outside_the_approved_layout(
    payload_store: PayloadStore, tmp_path: Path
) -> None:
    stray = tmp_path / "project" / "artifacts" / "working" / "app" / "resume.html"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"not a rendered output")

    with pytest.raises(ValueError, match="not an approved layout"):
        payload_store.ingest_render_output(stray)


def test_ingest_render_output_reports_a_render_target_that_was_never_written(
    payload_store: PayloadStore,
) -> None:
    missing = payload_store.output_path("app", "revision", "ghost", suffix="pdf")

    with pytest.raises(ArtifactPayloadMissing):
        payload_store.ingest_render_output(missing)
