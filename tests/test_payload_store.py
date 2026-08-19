from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from cv_engine.infrastructure.payloads import PayloadStore


@pytest.fixture
def payload_store(tmp_path: Path) -> PayloadStore:
    root = tmp_path / "workspace"
    workspace = SimpleNamespace(
        root=root,
        artifacts_root=root / "artifacts",
        temp_root=root / "tmp",
    )
    return PayloadStore(workspace)


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


def test_commit_stages_validates_hashes_renames_and_returns_registration_metadata(
    payload_store: PayloadStore,
) -> None:
    content = b"exact snapshot text\n"
    destination = payload_store.snapshot_path("app", "snapshot")
    observed: list[str] = []

    def write(path: Path) -> None:
        observed.append("write")
        assert "tmp/payloads" in path.as_posix()
        assert not destination.exists()
        path.write_bytes(content)

    def validate(path: Path) -> None:
        observed.append("validate")
        assert path.read_bytes() == content
        assert not destination.exists()

    stored = payload_store.commit(destination, write=write, validate=validate)

    assert observed == ["write", "validate"]
    assert stored.path == destination
    assert stored.workspace_relative == "artifacts/snapshots/app/snapshot.txt"
    assert stored.sha256 == hashlib.sha256(content).hexdigest()
    assert stored.size == len(content)
    assert destination.read_bytes() == content
    assert payload_store.temp_orphans() == []


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
            write=lambda path, content=content: path.write_bytes(content),
            validate=lambda path: path.is_file(),
        )
        assert stored.path.read_bytes() == content


def test_existing_immutable_payload_is_never_overwritten(
    payload_store: PayloadStore,
) -> None:
    destination = payload_store.snapshot_path("app", "snapshot")
    payload_store.commit(
        destination,
        write=lambda path: path.write_bytes(b"original"),
        validate=lambda _path: True,
    )

    with pytest.raises(FileExistsError, match="immutable payload already exists"):
        payload_store.commit(
            destination,
            write=lambda path: path.write_bytes(b"replacement"),
            validate=lambda _path: True,
        )
    assert destination.read_bytes() == b"original"


def test_revision_commit_reuses_only_exact_recovery_orphans(payload_store: PayloadStore) -> None:
    first = payload_store.commit_revision("app", "revision", '{"value":1}', "markdown")
    recovered = payload_store.commit_revision(
        "app", "revision", '{"value":1}', "markdown"
    )
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
            write=lambda path: path.write_bytes(b"no"),
            validate=lambda _path: True,
        )
    with pytest.raises(ValueError, match="contains traversal"):
        payload_store.commit(
            tmp_path
            / "workspace"
            / "artifacts"
            / "snapshots"
            / "app"
            / ".."
            / "outside"
            / "snapshot.txt",
            write=lambda path: path.write_bytes(b"no"),
            validate=lambda _path: True,
        )
    with pytest.raises(ValueError, match="not an approved layout"):
        payload_store.commit(
            "working/app/resume.md",
            write=lambda path: path.write_bytes(b"no"),
            validate=lambda _path: True,
        )
    with pytest.raises(ValueError, match="UUIDv4"):
        payload_store.commit(
            "manifests/latest.json",
            write=lambda path: path.write_bytes(b"no"),
            validate=lambda _path: True,
        )


def test_symlink_escapes_are_refused_before_a_write(
    payload_store: PayloadStore, tmp_path: Path
) -> None:
    artifacts = tmp_path / "workspace" / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts.mkdir(parents=True)
    (artifacts / "snapshots").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="path escapes configured root"):
        payload_store.snapshot_path("app", "snapshot")

    assert list(outside.iterdir()) == []


def test_failed_validation_leaves_an_aged_temp_orphan_without_deleting_it(
    payload_store: PayloadStore,
) -> None:
    destination = payload_store.snapshot_path("app", "snapshot")

    with pytest.raises(ValueError, match="payload validation failed"):
        payload_store.commit(
            destination,
            write=lambda path: path.write_bytes(b"invalid"),
            validate=lambda _path: False,
        )

    temp_path = next((destination.parents[3] / "tmp" / "payloads").iterdir())
    os.utime(temp_path, (100.0, 100.0))
    orphans = payload_store.temp_orphans(now=125.5)

    assert len(orphans) == 1
    assert orphans[0].path == temp_path
    assert orphans[0].workspace_relative.startswith("tmp/payloads/")
    assert orphans[0].age_seconds == 25.5
    assert orphans[0].size == len(b"invalid")
    assert temp_path.read_bytes() == b"invalid"
