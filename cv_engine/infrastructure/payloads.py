from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ..application.ports import PayloadReference
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


#: A payload writer is handed the bytes it must produce rather than a path to
#: write them to. The filesystem signature `Callable[[Path], object]` could not
#: survive a store that has no paths, and every caller was already producing
#: whole bytes and writing them in one call.
PayloadValidator = Callable[[bytes], bool | None]

#: Immutable payload references are project-relative POSIX strings
#: (`artifacts/submissions/app/id/resume.pdf`), and object keys are relative to
#: the artifact root (`submissions/app/id/resume.pdf`). The two differ by exactly
#: this prefix: Submission rows carry the reference, and the conversion happens
#: here rather than in every reader.
_REFERENCE_PREFIX = "artifacts"


@dataclass(frozen=True, slots=True)
class StoredPayload:
    """One committed immutable payload, as the registration boundary sees it."""

    project_relative: str
    sha256: str
    size: int


class PayloadStore:
    """Immutable v2 payload storage, independent of database registration."""

    _OUTPUT_SUFFIXES = {".html", ".pdf"}

    def __init__(self, paths: PayloadPaths, object_store: ObjectStore | None = None):
        """Storage is injected; application paths supply the local layout.

        `object_store` defaults to a `LocalObjectStore` over the application's
        artifact root, so a caller that configures nothing keeps exactly the
        behaviour it had. The roots stay because references are project-relative.
        """
        self._project_root = Path(paths.root).resolve()
        self._artifacts_root = resolve_within(self._project_root, paths.artifacts_root)
        self._objects = object_store or LocalObjectStore(self._artifacts_root)

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
        """The stored, project-relative reference for one object key."""
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
    ) -> PayloadReference:
        """Store one sent file under its Submission; an existing copy is never replaced."""
        stored = self.commit(
            self.submission_path(application_id, submission_id, suffix=suffix),
            payload=payload,
            validate=lambda content: bool(content),
        )
        return self._reference(stored)

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
            len(parts) == 4
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
            project_relative=self._reference_for_key(key),
            sha256=stored.sha256,
            size=stored.size,
        )

    def verify_payload(self, reference: str, expected_hash: str) -> str:
        """Classify one registered payload as ok, missing, tampered, or unresolvable.

        Ready qualification re-derives itself from stored evidence, and it used
        to do that by resolving the reference to a filesystem path and hashing
        the file. That was a read path into immutable payloads alongside
        `commit`, and the only one that never went through the store - so it verified the local disk no
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

    @staticmethod
    def _reference(stored: StoredPayload) -> PayloadReference:
        return PayloadReference(
            reference=stored.project_relative,
            sha256=stored.sha256,
            size=stored.size,
        )
