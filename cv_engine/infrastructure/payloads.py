from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ..application.errors import (
    ArtifactContainmentRefused,
    ArtifactHashMismatch,
    ArtifactPayloadMissing,
    InfrastructureFailure,
)
from ..application.ports import (
    ArtifactStream,
    SnapshotPayload,
)
from ..application.transactions import assert_external_io_allowed
from ..util import sha256_bytes
from .object_store import (
    LocalObjectStore,
    ObjectAlreadyExists,
    ObjectNotFound,
    ObjectStore,
)
from .paths import relative_within, resolve_within


class PayloadPaths(Protocol):
    @property
    def root(self) -> Path: ...

    @property
    def artifacts_root(self) -> Path: ...

    @property
    def temp_root(self) -> Path: ...


#: A payload writer is handed the bytes it must produce rather than a path to
#: write them to. The filesystem signature `Callable[[Path], object]` could not
#: survive a store that has no paths, and every caller was already producing
#: whole bytes and writing them in one call.
PayloadValidator = Callable[[bytes], bool | None]

#: Immutable payload references are project-relative POSIX strings
#: (`artifacts/snapshots/app/id.txt`), and object keys are relative to the
#: artifact root (`snapshots/app/id.txt`). The two differ by exactly this
#: prefix. The reference format is frozen - `artifact_versions` rows carry it
#: and `ArtifactStore.resolve` reads it - so the conversion happens here rather
#: than the stored string changing to match the key.
_REFERENCE_PREFIX = "artifacts"


@dataclass(frozen=True, slots=True)
class StoredPayload:
    """One committed immutable payload, as the registration boundary sees it.

    `path` stays a `Path` because `commit_revision` and the render targets are
    expressed in paths and because nothing outside this module reads it. It is
    derived from the key, never the other way round.
    """

    path: Path
    project_relative: str
    sha256: str
    size: int


class PayloadStore:
    """Immutable v2 payload storage, independent of database registration."""

    _OUTPUT_SUFFIXES = {".html", ".pdf"}
    #: Read size for streaming a payload outward. Bounded so a download
    #: never holds a whole artifact in memory the way a `read_bytes` would.
    _STREAM_CHUNK_BYTES = 64 * 1024

    def __init__(self, paths: PayloadPaths, object_store: ObjectStore | None = None):
        """Storage is injected; application paths supply the local layout.

        `object_store` defaults to a `LocalObjectStore` over the application's
        artifact root, so a caller that configures nothing keeps exactly the
        behaviour it had. The roots stay because references are project-relative
        and because `render_targets` must still hand
        Chromium a real path.
        """
        self._project_root = Path(paths.root).resolve()
        self._artifacts_root = resolve_within(self._project_root, paths.artifacts_root)
        self._temp_root = resolve_within(self._project_root, paths.temp_root)
        self._objects = object_store or LocalObjectStore(self._artifacts_root)

    def delete_payload(self, reference: str) -> None:
        """Remove one stored payload `reclaim_orphans` has decided is safe to remove.

        A reference that does not resolve to an approved, contained layout is
        refused (`ValueError`) rather than silently ignored - the same
        refusal every other reference-resolving method on this store makes.
        Within an approved layout, removal is idempotent: the key may already
        be gone.
        """
        assert_external_io_allowed("immutable payload removal")
        self._objects.delete(self._key_for_reference(reference))

    def payload_inventory(self, *, modified_before: datetime | None = None) -> list[str]:
        """List managed immutable references; working projections are excluded.

        No bytes are fetched and no objects are changed. Without
        `modified_before` this observation can include payloads whose writer
        has not registered them yet.
        """
        assert_external_io_allowed("payload inventory")
        references = []
        for key in self._objects.keys_under("", modified_before=modified_before):
            try:
                self._approved_destination(key)
            except ValueError:
                continue
            references.append(self._reference_for_key(key))
        return sorted(set(references))

    @staticmethod
    def _component(value: str, *, name: str) -> str:
        candidate = Path(value)
        if (
            not value
            or value in {".", ".."}
            or candidate.is_absolute()
            or len(candidate.parts) != 1
            or candidate.name != value
        ):
            raise ValueError(f"invalid {name} path component: {value}")
        return value

    def _target(self, *parts: str) -> Path:
        return resolve_within(self._artifacts_root, Path(*parts))

    def _key(self, destination: Path | str) -> str:
        """The object key for one approved destination.

        Goes through `_approved_destination` first, so the layout rules that
        guarded the filesystem still decide what is addressable. A key is only
        ever derived from a destination that already passed them.
        """
        approved = self._approved_destination(destination)
        return relative_within(self._artifacts_root, approved).as_posix()

    def _reference_for_key(self, key: str) -> str:
        """The stored reference for one object key.

        `artifact_versions` rows carry project-relative strings and
        `ArtifactStore.resolve` joins them onto the project root. That format
        is frozen, so the prefix is added here rather than the rows changing.
        """
        return f"{_REFERENCE_PREFIX}/{key}"

    def _key_for_reference(self, reference: str) -> str:
        """The object key for one stored reference, refusing anything else.

        A reference that does not sit under the artifact root is refused rather
        than coerced: a row pointing at a project file that is not an artifact
        payload must not become an addressable key.
        """
        candidate = resolve_within(self._project_root, reference)
        approved = self._approved_destination(candidate)
        return relative_within(self._artifacts_root, approved).as_posix()

    def _path_for_key(self, key: str) -> Path:
        return resolve_within(self._artifacts_root, key)

    def snapshot_path(self, application_id: str, snapshot_id: str) -> Path:
        return self._target(
            "snapshots",
            self._component(application_id, name="application_id"),
            f"{self._component(snapshot_id, name='snapshot_id')}.txt",
        )

    def reference_for(self, destination: Path) -> str:
        """The stored reference `destination` would receive, without writing anything.

        Pure and side-effect-free: it lets a caller compute the physical
        key(s) a write is about to produce *before* writing.
        """
        return self._reference_for_key(self._key(destination))

    def submission_path(self, application_id: str, submission_id: str, *, suffix: str) -> Path:
        """Where one Submission's copy of a rendered file belongs (state-and-use-cases §18).

        Submission-owned and immutable: the document's own rendered files are
        mutable working outputs that the next render or re-pin replaces, so what
        was sent is copied here rather than referenced there.
        """
        normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        if normalized_suffix not in self._OUTPUT_SUFFIXES:
            raise ValueError(f"unsupported submission file suffix: {suffix}")
        return self._target(
            "submissions",
            self._component(application_id, name="application_id"),
            self._component(submission_id, name="submission_id"),
            f"resume{normalized_suffix}",
        )

    def commit_submission_file(
        self, application_id: str, submission_id: str, *, suffix: str, payload: bytes
    ) -> SnapshotPayload:
        """Store one sent file under its Submission; an existing copy is never replaced."""
        stored = self.commit(
            self.submission_path(application_id, submission_id, suffix=suffix),
            payload=payload,
            validate=lambda content: bool(content),
        )
        return self._reference(stored)

    def provider_path(self, application_id: str, operation_id: str, artifact_id: str) -> Path:
        return self._target(
            "provider",
            self._component(application_id, name="application_id"),
            self._component(operation_id, name="operation_id"),
            f"{self._component(artifact_id, name='artifact_id')}.json",
        )

    def _approved_destination(self, candidate: Path | str) -> Path:
        unresolved = Path(candidate)
        if ".." in unresolved.parts:
            raise ValueError(f"payload destination contains traversal: {candidate}")
        if unresolved.is_absolute():
            relative = relative_within(self._artifacts_root, unresolved)
        else:
            relative = unresolved

        parts = relative.parts
        # The layouts of architecture §6.2, and no others.
        approved = (
            len(parts) == 3
            and parts[0] == "snapshots"
            and parts[2].endswith(".txt")
            or len(parts) == 4
            and parts[0] == "provider"
            and parts[3].endswith(".json")
            or len(parts) == 4
            and parts[0] == "submissions"
            and parts[3] in {"resume.html", "resume.pdf"}
        )
        if not approved:
            raise ValueError(f"payload destination is not an approved layout: {candidate}")
        return resolve_within(self._artifacts_root, relative)

    def commit(
        self,
        destination: Path | str,
        *,
        payload: bytes,
        validate: PayloadValidator,
    ) -> StoredPayload:
        """Validate, hash, and store one immutable payload under its key.

        The returned metadata is the registration boundary. The caller registers
        it in the database; a failure there deliberately leaves a safe stored
        orphan.

        There is no temp staging any more, and the ordering that staging used to
        provide is preserved rather than dropped. Validation runs on the bytes
        *before* anything is stored, so a payload that fails validation never
        occupies its key - which is what the old temp file bought, without the
        temp file. The bytes are hashed by the store as it writes them, so the
        digest describes what was stored rather than a file re-read afterwards.

        The overwrite refusal moved into the write itself. `LocalObjectStore`
        uses `O_EXCL` and the S3 store uses a conditional PUT, so the key is
        claimed atomically instead of being checked and then written - closing
        the window between the old `exists()` check and the `os.rename` that
        followed it.
        """
        assert_external_io_allowed("immutable payload write")
        key = self._key(destination)
        if validate(payload) is False:
            raise ValueError(f"payload validation failed: {destination}")
        try:
            stored = self._objects.put(key, payload)
        except ObjectAlreadyExists as exc:
            raise FileExistsError(f"immutable payload already exists: {key}") from exc

        return StoredPayload(
            path=self._path_for_key(key),
            project_relative=self._reference_for_key(key),
            sha256=stored.sha256,
            size=stored.size,
        )

    def commit_snapshot(
        self,
        application_id: str,
        snapshot_id: str,
        text: str,
    ) -> SnapshotPayload:
        stored = self.commit(
            self.snapshot_path(application_id, snapshot_id),
            payload=text.encode("utf-8"),
            validate=lambda _payload: True,
        )
        return SnapshotPayload(
            reference=stored.project_relative,
            sha256=stored.sha256,
            size=stored.size,
        )

    def commit_provider_response(
        self,
        application_id: str,
        operation_id: str,
        artifact_id: str,
        sanitized_json: str,
    ) -> SnapshotPayload:
        """Preserve one sanitized provider response as an immutable payload.

        The layout - `provider/{application_id}/{operation_id}/{artifact_id}.json`
        - is the one architecture §6.2 already approves, and it was already the
        one `_approved_destination` accepts; Stage G is the first caller. The
        Operation ID is in the path so a retry, which is a second Operation,
        cannot land on the first one's evidence.

        The bytes are sanitized before they arrive. This method does not inspect
        them for secrets, because a store that re-derived that rule could
        disagree with the adapter that applied it; it validates that they parse
        as JSON, which is what the approved layout promises about the file.

        Database registration stays with the caller, exactly as it does for
        revisions and archived drafts: a failure there leaves a reconcilable
        filesystem orphan rather than a pointer to nothing.
        """
        stored = self.commit(
            self.provider_path(application_id, operation_id, artifact_id),
            payload=sanitized_json.encode("utf-8"),
            validate=self._valid_json,
        )
        return self._reference(stored)

    def open_artifact(self, reference: str, expected_hash: str) -> ArtifactStream:
        """Verify one registered immutable payload and hand back exactly those bytes.

        The order is the point. Containment first, through `resolve_within`,
        which resolves symlinks before it compares - so a link inside the
        artifact root pointing anywhere else is refused by the same check that
        refuses `..`, rather than by a second rule that could disagree with it.
        Then the approved-layout check, so a row pointing at a project file
        that is not an artifact payload cannot be served. Then the payload is
        read once, and the hash is computed over the bytes that were read.

        **The hash covers the bytes this returns, not the file it came from.**
        Verifying the path and then reopening it to stream would leave a
        time-of-check/time-of-use window: replace the payload in between and the
        client receives unverified bytes under the previous `ETag` and
        `Content-Length`, or the file disappears and the read fails after a
        `200` and its headers have already gone out. Holding an open descriptor
        does not close that window either - `Path.write_bytes` truncates and
        rewrites the *same inode*, so a held handle would read the substituted
        content. Capturing the payload and hashing what was captured is what
        makes the guarantee hold, and it collapses two reads into one.

        The buffer is the whole payload. That is affordable because artifacts
        here are one-page CV documents and manifests that this
        system produced itself - architecture §14 admits no file uploads and no
        arbitrary paths, so there is no route by which an unbounded payload
        reaches this method.

        The refusals are classified here because this is the only place that
        knows which of the three checks failed, and each message names the
        check rather than the path: what fails containment is exactly what must
        not be echoed back to a client.

        No `Path` leaves this method.
        """
        try:
            key = self._key_for_reference(reference)
        except ValueError as exc:
            raise ArtifactContainmentRefused(
                "the registered artifact path does not resolve to a contained "
                "payload inside the artifact root"
            ) from exc
        try:
            payload = self._objects.get(key)
        except ObjectNotFound as exc:
            raise ArtifactPayloadMissing("the registered artifact payload is not stored") from exc
        except InfrastructureFailure:
            raise
        except OSError as exc:
            raise InfrastructureFailure(
                "the registered artifact payload could not be read"
            ) from exc
        actual_hash = sha256_bytes(payload)
        if actual_hash != expected_hash:
            raise ArtifactHashMismatch(
                f"artifact payload hash mismatch: expected {expected_hash}, got {actual_hash}"
            )

        def chunks() -> Iterator[bytes]:
            for offset in range(0, len(payload), self._STREAM_CHUNK_BYTES):
                yield payload[offset : offset + self._STREAM_CHUNK_BYTES]

        return ArtifactStream(size=len(payload), chunks=chunks)

    def verify_payload(self, reference: str, expected_hash: str) -> str:
        """Classify one registered payload as ok, missing, tampered, or unresolvable.

        Ready qualification re-derives itself from stored evidence, and it used
        to do that by resolving the reference to a filesystem path and hashing
        the file. That is a fourth read path into immutable payloads, alongside
        `open_artifact`, `read_snapshot` and `commit`, and it is the only one
        that never went through the store - so it verified the local disk no
        matter what storage was configured, and would have reported every
        payload missing once storage moved off it.

        The classification is returned rather than raised because Ready
        qualification records each failure as an issue and continues, so it can
        report every unmet condition at once instead of the first one. A
        reference that does not resolve to an approved payload is
        `unresolvable`, which keeps a malformed row distinguishable from a
        payload that is genuinely absent.
        """
        try:
            key = self._key_for_reference(reference)
        except ValueError:
            return "unresolvable"
        try:
            payload = self._objects.get(key)
        except ObjectNotFound:
            return "missing"
        return "ok" if sha256_bytes(payload) == expected_hash else "tampered"

    def read_snapshot(self, reference: str, expected_hash: str) -> str:
        key = self._key_for_reference(reference)
        if len(key.split("/")) != 3 or not key.startswith("snapshots/"):
            raise ValueError(f"payload is not a JobSnapshot: {reference}")
        try:
            payload = self._objects.get(key)
        except ObjectNotFound as exc:
            raise FileNotFoundError(f"snapshot payload does not exist: {reference}") from exc
        actual_hash = sha256_bytes(payload)
        if actual_hash != expected_hash:
            raise ValueError(
                f"snapshot payload hash mismatch: expected {expected_hash}, got {actual_hash}"
            )
        return payload.decode("utf-8")

    @staticmethod
    def _reference(stored: StoredPayload) -> SnapshotPayload:
        return SnapshotPayload(
            reference=stored.project_relative,
            sha256=stored.sha256,
            size=stored.size,
        )

    @staticmethod
    def _valid_json(payload: bytes) -> bool:
        json.loads(payload.decode("utf-8"))
        return True
