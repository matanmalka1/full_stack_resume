from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
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
    RenderTargets,
    RevisionPayloads,
    SnapshotPayload,
)
from ..util import sha256_bytes
from .object_store import (
    LocalObjectStore,
    ObjectAlreadyExists,
    ObjectNotFound,
    ObjectStore,
    validate_key,
)
from .paths import relative_within, resolve_within


class PayloadWorkspace(Protocol):
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

#: Immutable payload references are Workspace-relative POSIX strings
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
    workspace_relative: str
    sha256: str
    size: int


@dataclass(frozen=True)
class _PayloadRoots:
    root: Path
    artifacts_root: Path
    temp_root: Path

class PayloadStore:
    """Immutable v2 payload storage, independent of database registration."""

    _OUTPUT_SUFFIXES = {".html", ".pdf", ".png"}
    #: Read size for streaming a payload outward. Bounded so a download
    #: never holds a whole artifact in memory the way a `read_bytes` would.
    _STREAM_CHUNK_BYTES = 64 * 1024

    def __init__(self, workspace: PayloadWorkspace, object_store: ObjectStore | None = None):
        """Storage is injected; the Workspace still supplies the layout.

        `object_store` defaults to a `LocalObjectStore` over the Workspace's
        artifact root, so a caller that configures nothing keeps exactly the
        behaviour it had. The Workspace roots stay because references are
        Workspace-relative and because `render_targets` must still hand
        Chromium a real path.
        """
        self._workspace_root = Path(workspace.root).resolve()
        self._artifacts_root = resolve_within(self._workspace_root, workspace.artifacts_root)
        self._temp_root = resolve_within(self._workspace_root, workspace.temp_root)
        self._objects = object_store or LocalObjectStore(self._artifacts_root)

    @classmethod
    def for_workspace_root(cls, root: Path) -> PayloadStore:
        resolved = Path(root).resolve()
        return cls(
            _PayloadRoots(
                root=resolved,
                artifacts_root=resolved / "artifacts",
                temp_root=resolved / "tmp",
            )
        )

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

        `artifact_versions` rows carry Workspace-relative strings and
        `ArtifactStore.resolve` joins them onto the Workspace root. That format
        is frozen, so the prefix is added here rather than the rows changing.
        """
        return f"{_REFERENCE_PREFIX}/{key}"

    def _key_for_reference(self, reference: str) -> str:
        """The object key for one stored reference, refusing anything else.

        A reference that does not sit under the artifact root is refused rather
        than coerced: a row pointing at a Workspace file that is not an artifact
        payload must not become an addressable key.
        """
        candidate = resolve_within(self._workspace_root, reference)
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

    def revision_path(self, application_id: str, revision_id: str, *, format: str) -> Path:
        if format not in {"json", "md"}:
            raise ValueError(f"unsupported revision format: {format}")
        return self._target(
            "revisions",
            self._component(application_id, name="application_id"),
            self._component(revision_id, name="revision_id"),
            f"resume.{format}",
        )

    def draft_snapshot_path(
        self, application_id: str, working_draft_id: str, edit_version: int
    ) -> Path:
        """Where one archived WorkingDraft version's immutable payload lives.

        The edit version is part of the filename rather than a directory, so a
        second archive of the same draft at a later version is a new immutable
        file and archiving the same version twice collides instead of
        overwriting evidence.
        """
        if edit_version < 1:
            raise ValueError(f"invalid working draft edit version: {edit_version}")
        return self._target(
            "drafts",
            self._component(application_id, name="application_id"),
            f"{self._component(working_draft_id, name='working_draft_id')}-v{edit_version}.json",
        )

    def output_path(
        self,
        application_id: str,
        revision_id: str,
        artifact_id: str,
        *,
        suffix: str,
    ) -> Path:
        normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        if normalized_suffix not in self._OUTPUT_SUFFIXES:
            raise ValueError(f"unsupported output suffix: {suffix}")
        return self._target(
            "outputs",
            self._component(application_id, name="application_id"),
            self._component(revision_id, name="revision_id"),
            f"{self._component(artifact_id, name='artifact_id')}{normalized_suffix}",
        )

    def render_targets(
        self,
        application_id: str,
        revision_id: str,
        html_artifact_version_id: str,
        pdf_artifact_version_id: str,
        screenshot_artifact_version_id: str,
        recruiter_pdf_filename: str,
    ) -> RenderTargets:
        return RenderTargets(
            html=self._render_location(
                self.output_path(
                    application_id, revision_id, html_artifact_version_id, suffix="html"
                )
            ),
            pdf=self._render_location(
                self.output_path(application_id, revision_id, pdf_artifact_version_id, suffix="pdf")
            ),
            screenshot=self._render_location(
                self.output_path(
                    application_id, revision_id, screenshot_artifact_version_id, suffix="png"
                )
            ),
            recruiter_pdf_filename=recruiter_pdf_filename,
        )

    def _render_location(self, destination: Path) -> Path:
        """Where Chromium writes the output destined for `destination`.

        The store decides. On the local store this is the artifact path itself,
        so the render target *is* the stored object and nothing is written
        twice. On a remote store it is scratch under the Workspace temp root,
        which `ingest_render_output` uploads and then removes.
        """
        return self._objects.render_location(self._key(destination), self._temp_root)

    def ingest_render_output(self, path: Path) -> SnapshotPayload:
        """Take one rendered output into storage, keyed by where it belongs.

        The three rendered outputs are the one payload family that cannot go
        through `commit`: Chromium writes them itself, to the paths
        `render_targets` hands it, so they exist as files before the store ever
        sees them. Everything else about them is the same - they are immutable,
        they are registered in `artifact_versions`, and they are served back
        through `open_artifact` - so they belong under the same keys, with the
        same containment rules and the same reference format.

        `path` is the render target the caller was handed, which may be the
        artifact location or scratch, depending on the backend. The key is
        recovered by asking the store where each approved output would have been
        rendered and matching - rather than deriving a key from the path, which
        only works while the two coincide. An unapproved layout still cannot be
        ingested, because the candidate keys come from `output_path`.

        The bytes are read once and that read is what is stored and what is
        hashed; the caller registers this digest rather than re-hashing the
        file, so the recorded hash describes what storage holds rather than what
        the filesystem held a moment later. Scratch is removed afterwards, and
        only when the store says the file was scratch: on the local store the
        rendered file *is* the payload and deleting it would destroy the
        artifact the row points at.

        A `Path` travels inward here and nothing carrying one travels back:
        the return value is the same storage-neutral `SnapshotPayload` that
        every other commit produces.
        """
        rendered = Path(path)
        key = self._key_for_render_location(rendered)
        try:
            stored = self._objects.ingest(key, rendered)
        except ObjectNotFound as exc:
            raise ArtifactPayloadMissing(
                "the rendered output was not written to its render target"
            ) from exc
        except ObjectAlreadyExists as exc:
            raise FileExistsError(f"immutable payload already exists: {key}") from exc
        self._objects.render_cleanup(rendered)
        return SnapshotPayload(
            reference=self._reference_for_key(key),
            sha256=stored.sha256,
            size=stored.size,
        )

    def _key_for_render_location(self, rendered: Path) -> str:
        """The object key one render location belongs to.

        On the local store the render location is the artifact path, so the key
        derives from it directly. On a remote store it is scratch named after
        the key, so the key is read back out of it and then validated against
        the approved layout - never trusted as a path.
        """
        try:
            return self._key(rendered)
        except ValueError:
            staging = resolve_within(self._temp_root, "render")
            try:
                relative = relative_within(staging, rendered).as_posix()
            except ValueError as exc:
                raise ValueError(
                    f"payload destination is not an approved layout: {rendered}"
                ) from exc
            return self._key(self._path_for_key(validate_key(relative)))

    def provider_path(self, application_id: str, operation_id: str, artifact_id: str) -> Path:
        return self._target(
            "provider",
            self._component(application_id, name="application_id"),
            self._component(operation_id, name="operation_id"),
            f"{self._component(artifact_id, name='artifact_id')}.json",
        )

    def manifest_path(self, manifest_id: str) -> Path:
        component = self._component(manifest_id, name="manifest_id")
        self._require_uuid4(component)
        return self._target("manifests", f"{component}.json")

    @staticmethod
    def _require_uuid4(value: str) -> None:
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise ValueError(f"manifest_id must be a UUIDv4: {value}") from exc
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError(f"manifest_id must be a UUIDv4: {value}")

    def _approved_destination(self, candidate: Path | str) -> Path:
        unresolved = Path(candidate)
        if ".." in unresolved.parts:
            raise ValueError(f"payload destination contains traversal: {candidate}")
        if unresolved.is_absolute():
            relative = relative_within(self._artifacts_root, unresolved)
        else:
            relative = unresolved

        parts = relative.parts
        manifest_id = Path(parts[1]).stem if len(parts) == 2 else None
        approved = (
            len(parts) == 3
            and parts[0] == "snapshots"
            and parts[2].endswith(".txt")
            or len(parts) == 4
            and parts[0] == "revisions"
            and parts[3] in {"resume.json", "resume.md"}
            or len(parts) == 4
            and parts[0] == "outputs"
            and Path(parts[3]).suffix in self._OUTPUT_SUFFIXES
            or len(parts) == 4
            and parts[0] == "provider"
            and parts[3].endswith(".json")
            or len(parts) == 2
            and parts[0] == "manifests"
            and parts[1].endswith(".json")
            or len(parts) == 3
            and parts[0] == "drafts"
            and parts[2].endswith(".json")
        )
        if not approved:
            raise ValueError(f"payload destination is not an approved layout: {candidate}")
        if manifest_id is not None and parts[0] == "manifests":
            self._require_uuid4(manifest_id)
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
        key = self._key(destination)
        if validate(payload) is False:
            raise ValueError(f"payload validation failed: {destination}")
        try:
            stored = self._objects.put(key, payload)
        except ObjectAlreadyExists as exc:
            raise FileExistsError(f"immutable payload already exists: {key}") from exc

        return StoredPayload(
            path=self._path_for_key(key),
            workspace_relative=self._reference_for_key(key),
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
            reference=stored.workspace_relative,
            sha256=stored.sha256,
            size=stored.size,
        )

    def commit_draft_snapshot(
        self,
        application_id: str,
        working_draft_id: str,
        edit_version: int,
        structured_json: str,
    ) -> SnapshotPayload:
        """Materialize one archived WorkingDraft version as an immutable payload.

        Database registration stays with the caller, exactly as it does for
        revisions: a failure there leaves a safe filesystem orphan rather than
        an archived pointer with nothing behind it.
        """
        stored = self.commit(
            self.draft_snapshot_path(application_id, working_draft_id, edit_version),
            payload=structured_json.encode("utf-8"),
            validate=self._valid_json,
        )
        return self._reference(stored)

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
        Then the approved-layout check, so a row pointing at a Workspace file
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
        here are one-page CV documents, screenshots and manifests that this
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

    def read_payload_text(self, reference: str) -> str:
        """Return one registered immutable payload as text.

        `read_snapshot` is deliberately JobSnapshot-only - it refuses anything
        that is not a snapshot layout - and `open_artifact` is the verified
        outward-facing download path. Ready qualification needs neither: it
        reads a registered claim manifest it has already verified by hash a few
        lines earlier, to re-derive the draft bindings from it. Reading it back
        off the local filesystem was the last thing in that function still
        bypassing the store.

        No hash argument, because the caller has already checked it and a
        second check here would be a different read from the one it verified.
        """
        key = self._key_for_reference(reference)
        try:
            return self._objects.get(key).decode("utf-8")
        except ObjectNotFound as exc:
            raise ArtifactPayloadMissing("the registered artifact payload is not stored") from exc

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
            reference=stored.workspace_relative,
            sha256=stored.sha256,
            size=stored.size,
        )

    @staticmethod
    def _valid_json(payload: bytes) -> bool:
        json.loads(payload.decode("utf-8"))
        return True

    def commit_revision(
        self,
        application_id: str,
        revision_id: str,
        structured_json: str,
        markdown: str,
    ) -> RevisionPayloads:
        """Commit and re-hash both immutable ApprovedRevision payloads.

        Database registration is deliberately left to the caller. If either
        registration later fails, these files are safe reconciliation orphans.
        """

        def commit_or_reuse(
            destination: Path, content: bytes, validator: PayloadValidator
        ) -> StoredPayload:
            key = self._key(destination)
            if self._objects.exists(key):
                existing = self._objects.get(key)
                if existing != content:
                    raise FileExistsError(
                        f"immutable payload already exists with different content: {destination}"
                    )
                if validator(existing) is False:
                    raise ValueError(f"existing immutable payload failed validation: {destination}")
                return StoredPayload(
                    path=self._path_for_key(key),
                    workspace_relative=self._reference_for_key(key),
                    sha256=sha256_bytes(existing),
                    size=len(existing),
                )
            return self.commit(destination, payload=content, validate=validator)

        structured = commit_or_reuse(
            self.revision_path(application_id, revision_id, format="json"),
            structured_json.encode("utf-8"),
            self._valid_json,
        )
        rendered = commit_or_reuse(
            self.revision_path(application_id, revision_id, format="md"),
            markdown.encode("utf-8"),
            lambda _payload: True,
        )
        for stored in (structured, rendered):
            actual = self._objects.stat(self._key_for_reference(stored.workspace_relative)).sha256
            if actual != stored.sha256:
                raise ValueError(
                    "committed revision payload hash mismatch: "
                    f"expected {stored.sha256}, got {actual}"
                )
        return RevisionPayloads(
            structured=self._reference(structured),
            markdown=self._reference(rendered),
        )
