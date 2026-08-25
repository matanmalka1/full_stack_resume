from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any

import pytest

from cv_engine.infrastructure.object_store import (
    LocalObjectStore,
    ObjectAlreadyExists,
    ObjectKeyRefused,
    ObjectNotFound,
    S3ObjectStore,
    validate_key,
)


class _ClientError(Exception):
    """Shaped like a botocore ClientError: the code lives in `response`."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeS3:
    """An S3 with the two semantics this store depends on.

    Conditional PUT and per-key absence. A real bucket is what the smoke run
    exercises; this exists so the *refusals* are covered without a network.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(
        self, Bucket: str, Key: str, Body: bytes, IfNoneMatch: str | None = None
    ) -> dict[str, Any]:
        if IfNoneMatch == "*" and Key in self.objects:
            raise _ClientError("PreconditionFailed")
        self.objects[Key] = Body
        return {}

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise _ClientError("404")
        return {}


@pytest.fixture
def local(tmp_path: Path) -> LocalObjectStore:
    return LocalObjectStore(tmp_path / "artifacts")


@pytest.fixture
def s3() -> S3ObjectStore:
    return S3ObjectStore("bucket", prefix="cv", client=_FakeS3())


def _stores(local: LocalObjectStore, s3: S3ObjectStore) -> list[Any]:
    return [local, s3]


@pytest.mark.parametrize(
    "key",
    ["", "/absolute/key", "a//b", "a/../b", "..", "a/./b", "back\\slash", "C:/drive", " pad", "t/"],
)
def test_crafted_keys_are_refused(key: str) -> None:
    """The refusals are the store's, not the filesystem's.

    "S3 has no `..`" is not a reason to weaken them: if the two backends
    disagreed about which keys are addressable, a payload's address would
    depend on which backend happened to be configured.
    """
    with pytest.raises(ObjectKeyRefused):
        validate_key(key)


def test_both_backends_refuse_to_overwrite_an_immutable_payload(
    local: LocalObjectStore, s3: S3ObjectStore
) -> None:
    for store in _stores(local, s3):
        store.put("snapshots/app/snap.txt", b"original")
        with pytest.raises(ObjectAlreadyExists):
            store.put("snapshots/app/snap.txt", b"replacement")
        assert store.get("snapshots/app/snap.txt") == b"original"


def test_both_backends_agree_on_hash_size_and_absence(
    local: LocalObjectStore, s3: S3ObjectStore
) -> None:
    digests = set()
    for store in _stores(local, s3):
        stored = store.put("revisions/app/rev/resume.md", b"# markdown\n")
        digests.add((stored.sha256, stored.size))
        assert store.exists("revisions/app/rev/resume.md")
        assert not store.exists("revisions/app/rev/missing.md")
        with pytest.raises(ObjectNotFound):
            store.get("revisions/app/rev/missing.md")
        with pytest.raises(ObjectNotFound):
            store.stat("revisions/app/rev/missing.md")
    assert len(digests) == 1, "the two backends disagreed about content identity"


def test_s3_applies_its_prefix_to_the_bucket_key_only(s3: S3ObjectStore) -> None:
    """The prefix is bucket layout, not part of the payload's identity.

    It is also applied *after* validation: validating the joined string would
    judge a crafted key against a different subject than the one stored.
    """
    stored = s3.put("snapshots/app/snap.txt", b"x")

    assert stored.key == "snapshots/app/snap.txt"
    assert list(s3._client.objects) == ["cv/snapshots/app/snap.txt"]  # type: ignore[attr-defined]


def test_ingest_reports_a_source_that_was_never_written(
    local: LocalObjectStore, s3: S3ObjectStore
) -> None:
    missing = Path(tempfile.gettempdir()) / "definitely-not-written-by-any-renderer.html"
    for store in _stores(local, s3):
        with pytest.raises(ObjectNotFound):
            store.ingest("outputs/app/rev/id.html", missing)
