from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..application.errors import InfrastructureFailure
from ..util import sha256_bytes
from .paths import resolve_within


class ObjectKeyRefused(ValueError):
    """A key is not something this store will address.

    A `ValueError`, because that is what the filesystem store raised for the
    same refusals and what `PayloadStore` callers and tests already expect from
    a bad component or an unapproved layout. The subclass exists so a caller
    that wants to distinguish "the key is malformed" from "the payload failed
    validation" can, without every such caller matching on a message.
    """


class ObjectAlreadyExists(FileExistsError):
    """A key that is already occupied was offered a second payload.

    `FileExistsError` rather than a new base, because refusing to overwrite an
    immutable payload is the existing contract: `commit` raises it today and
    the rendering service maps it onto `StateConflict`. An object store that
    raised something else would silently change that mapping.
    """


class ObjectNotFound(Exception):
    """No payload is stored under this key."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    """What a store knows about one payload the moment it was written.

    The hash is computed over the bytes that were stored, by the store, rather
    than taken from the caller: a hash the caller supplied would prove only
    what the caller believed it sent.
    """

    key: str
    sha256: str
    size: int


class ObjectStore(Protocol):
    """Keys and bytes. No `Path`, no directories, no temp staging.

    The unit is a whole payload, because every immutable payload in this system
    is one document that the system produced itself - a CV, a screenshot, a
    manifest, a sanitized provider response. Architecture §14 admits no
    uploads and no arbitrary paths, so there is no route by which an unbounded
    payload reaches an implementation of this protocol.

    A key is a `/`-separated relative string. It is not a path: an
    implementation must not interpret `..`, a leading `/`, a drive letter, or a
    backslash as structure, and must refuse a key containing any of them
    (`validate_key`). The local implementation happens to map a key onto a path,
    and that mapping is exactly where a crafted key would become a traversal, so
    the refusal lives in the protocol's contract rather than in one adapter's
    discretion.
    """

    def put(self, key: str, payload: bytes) -> StoredObject:
        """Store `payload` under `key`, refusing to replace an existing object.

        Atomic at the object level and never partially visible. Raises
        `ObjectAlreadyExists` when the key is occupied - immutable payloads are
        never silently replaced.
        """
        ...

    def get(self, key: str) -> bytes:
        """Return the whole payload stored under `key`.

        One read. A caller that needs the hash of what it received must compute
        it over these bytes, not reopen the key, or it reintroduces the
        time-of-check/time-of-use window `PayloadStore.open_artifact` exists to
        close. Raises `ObjectNotFound` when the key holds nothing.
        """
        ...

    def exists(self, key: str) -> bool: ...

    def stat(self, key: str) -> StoredObject:
        """Metadata for a stored object without transferring its bytes.

        Raises `ObjectNotFound` when the key holds nothing.
        """
        ...

    def ingest(self, key: str, source: Path) -> StoredObject:
        """Store the contents of a local file under `key`.

        The one method that admits a `Path`, and it admits one inward only.
        Chromium writes rendered HTML, PDFs and screenshots to real paths
        because it cannot write to an object store, so those payloads reach
        storage as a location rather than as bytes. Nothing carrying a `Path`
        comes back.

        The hash describes the bytes that were stored, read once. Raises
        `ObjectNotFound` when `source` does not exist, and `ObjectAlreadyExists`
        when the key is already occupied - a rendered output must not silently
        replace a registered one.
        """
        ...

    def render_location(self, key: str, staging_root: Path) -> Path:
        """Where Chromium should write the payload destined for `key`.

        The store decides, because only the store knows whether that location
        *is* the stored object. On a filesystem store it is: the render writes
        straight to the artifact root and ingest is a read. On a remote store it
        is scratch space that ingest uploads from.

        `render_cleanup` answers the consequence of that difference, and the two
        must be read together: deleting the render location is correct in the
        second case and destroys the payload in the first.

        The returned location is ready to be written to: the store creates any
        directory the renderer would need. Chromium is handed this path and
        writes to it directly, so a location whose parent does not exist is not
        a location - it is a `FileNotFoundError` the renderer raises.
        """
        ...

    def render_cleanup(self, path: Path) -> bool:
        """Whether `path` is scratch to delete after ingest, and delete it.

        Returns True when the file was scratch and has been removed, False when
        the render location is the stored object and must be left alone.
        """
        ...


def validate_key(key: str) -> str:
    """Refuse any key that could become a traversal, then return it unchanged.

    The refusals are the ones `PayloadStore._component` and `resolve_within`
    make today, restated for keys, and they are made here - before any
    implementation touches the key - so the local and remote stores cannot
    disagree about which keys are addressable. "S3 has no `..`" is not a reason
    to drop the check: the same crafted key must be refused by both stores, or a
    payload's address depends on which backend is configured.
    """
    if not key:
        raise ObjectKeyRefused("object key is empty")
    if key != key.strip():
        raise ObjectKeyRefused(f"object key has leading or trailing whitespace: {key!r}")
    if "\\" in key:
        raise ObjectKeyRefused(f"object key contains a backslash: {key}")
    if "\x00" in key:
        raise ObjectKeyRefused(f"object key contains a null byte: {key!r}")
    if key.startswith("/") or key.endswith("/"):
        raise ObjectKeyRefused(f"object key is not relative: {key}")
    if "//" in key:
        raise ObjectKeyRefused(f"object key has an empty segment: {key}")
    segments = key.split("/")
    for segment in segments:
        if segment in {".", ".."}:
            raise ObjectKeyRefused(f"object key contains traversal: {key}")
    # A Windows drive prefix would be absolute on a filesystem store and inert
    # on S3. Refusing it keeps one answer for both.
    if len(segments[0]) == 2 and segments[0][1] == ":":
        raise ObjectKeyRefused(f"object key is not relative: {key}")
    return key


class LocalObjectStore:
    """`ObjectStore` over one filesystem root. The default backend.

    Behaviour-identical to what `PayloadStore` did with the filesystem
    directly, minus the temp-file staging: a key maps to a path under `root`,
    resolved through `resolve_within`, so a symlink escape is refused by the
    same check that refuses `..` rather than by a second rule that could
    disagree with it.

    There is no temp-then-rename. `put` writes with `O_EXCL`, which is the
    filesystem's own atomic "create or fail" and is what makes the overwrite
    refusal a property of the write rather than a check that races it. The
    partially-visible-file window that temp staging existed to close is closed
    differently here: a failed write leaves no object under the key at all,
    because the caller's bytes are complete before `put` is called.
    """

    def __init__(self, root: Path):
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        """The filesystem root. For composition and diagnostics only.

        Deliberately not on the `ObjectStore` protocol: no `Path` may reach a
        caller that speaks the protocol, or the abstraction is decorative.
        """
        return self._root

    def _path(self, key: str) -> Path:
        return resolve_within(self._root, validate_key(key))

    def put(self, key: str, payload: bytes) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Re-resolve after `mkdir`: the parent did not exist for the first
        # check, so a symlink planted as one of those components could only be
        # caught now.
        path = resolve_within(self._root, path)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise ObjectAlreadyExists(f"immutable payload already exists: {key}") from exc
        except OSError as exc:
            raise InfrastructureFailure(f"object could not be written: {key}") from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
        except OSError as exc:
            raise InfrastructureFailure(f"object could not be written: {key}") from exc
        return StoredObject(key=key, sha256=sha256_bytes(payload), size=len(payload))

    def get(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(f"no object is stored under {key}") from exc
        except IsADirectoryError as exc:
            raise ObjectNotFound(f"no object is stored under {key}") from exc
        except OSError as exc:
            raise InfrastructureFailure(f"object could not be read: {key}") from exc

    def exists(self, key: str) -> bool:
        try:
            path = self._path(key)
        except ValueError:
            return False
        return path.is_file() and not path.is_symlink()

    def stat(self, key: str) -> StoredObject:
        path = self._path(key)
        try:
            size = path.stat().st_size
        except FileNotFoundError as exc:
            raise ObjectNotFound(f"no object is stored under {key}") from exc
        except OSError as exc:
            raise InfrastructureFailure(f"object could not be read: {key}") from exc
        if not path.is_file():
            raise ObjectNotFound(f"no object is stored under {key}")
        return StoredObject(key=key, sha256=sha256_bytes(path.read_bytes()), size=size)

    def ingest(self, key: str, source: Path) -> StoredObject:
        """Take a file the renderer wrote and store it under `key`.

        On this store the renderer already wrote to the destination path, so
        the file is where it belongs and ingesting it is a read: the bytes are
        read once, and that read is what the hash describes. Copying it onto
        itself would be a no-op with a truncation window in the middle.

        When the source is somewhere else - which is what a remote store always
        sees, and what this store sees if the renderer is ever pointed at a
        scratch directory - the bytes are put under the key normally, so the
        overwrite refusal still applies.
        """
        path = self._path(key)
        resolved_source = Path(source).resolve()
        if not resolved_source.is_file():
            raise ObjectNotFound(f"no file to ingest at {source}")
        if resolved_source == path:
            payload = resolved_source.read_bytes()
            return StoredObject(key=key, sha256=sha256_bytes(payload), size=len(payload))
        return self.put(key, resolved_source.read_bytes())

    def render_location(self, key: str, staging_root: Path) -> Path:  # noqa: ARG002
        """The artifact path itself: here the render target is the stored object.

        `staging_root` is accepted and ignored deliberately - the protocol
        passes it because a remote store needs it. Rendering into scratch and
        then copying would write every artifact twice on the one backend where
        the copy buys nothing, and would reintroduce the temp-then-publish step
        this design removed.

        The parent directory is created here because this is where the render
        location is decided. `put` creates it for a payload that arrives as
        bytes, but a rendered output never passes through `put` on this store -
        ingest reads it in place - so nothing else would.
        """
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return resolve_within(self._root, path)

    def render_cleanup(self, path: Path) -> bool:  # noqa: ARG002
        """Never. On this store the rendered file *is* the payload.

        Deleting it after ingest would delete the artifact the row points at,
        which is why this returns False rather than doing nothing quietly: the
        caller is told the file was kept on purpose.
        """
        return False

    def keys_under(self, prefix: str) -> Iterator[str]:
        """Every key stored beneath `prefix`, in sorted order.

        Reconciliation reads this. It is not on the protocol until something
        needs it from both backends.
        """
        base = resolve_within(self._root, validate_key(prefix)) if prefix else self._root
        if not base.is_dir():
            return
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink():
                yield path.relative_to(self._root).as_posix()


class S3ObjectStore:
    """`ObjectStore` over an S3-compatible bucket. R2 via `endpoint_url`.

    boto3 is imported inside `__init__` rather than at module scope, because
    the local path must keep working with no cloud SDK installed - the
    deterministic workflow has to reach Ready with nothing configured, and a
    module-level import would make that depend on an optional dependency.

    Every botocore exception is translated. One escaping raw would reach the
    application layer as something it has no case for, and architecture §14's
    error taxonomy would then depend on which backend is configured.
    """

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "",
        endpoint_url: str | None = None,
        region_name: str | None = None,
        client: object | None = None,
    ):
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        if client is not None:
            self._client = client
            return
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on the install extra
            raise InfrastructureFailure(
                "object storage is configured for S3 but boto3 is not installed; "
                "install the 's3' extra"
            ) from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
        )

    def _object_key(self, key: str) -> str:
        """The bucket key for one store key.

        The prefix is applied after validation, never before: validating the
        joined string would let a crafted key be judged against a different
        subject than the one that gets stored.
        """
        validated = validate_key(key)
        return f"{self._prefix}/{validated}" if self._prefix else validated

    def _client_error(self, exc: Exception) -> str:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        return str(code)

    def put(self, key: str, payload: bytes) -> StoredObject:
        """Conditional PUT. No temp key, no copy.

        `IfNoneMatch: "*"` makes the overwrite refusal the server's decision
        rather than a read-then-write this client could lose a race on. S3 and
        R2 both support it, and a precondition failure maps onto the same
        `ObjectAlreadyExists` the local store raises.

        There is no temp-then-copy staging: a PutObject is atomic at the object
        level and S3 has provided strong read-after-write consistency since
        December 2020, so the partial-write window that staging existed to
        close does not exist here. CopyObject is not atomic anyway.
        """
        object_key = self._object_key(key)
        try:
            self._client.put_object(  # type: ignore[attr-defined]
                Bucket=self._bucket,
                Key=object_key,
                Body=payload,
                IfNoneMatch="*",
            )
        except Exception as exc:
            code = self._client_error(exc)
            if code in {"PreconditionFailed", "ConditionalRequestConflict", "412"}:
                raise ObjectAlreadyExists(f"immutable payload already exists: {key}") from exc
            raise InfrastructureFailure(f"object could not be written: {key}") from exc
        return StoredObject(key=key, sha256=sha256_bytes(payload), size=len(payload))

    def get(self, key: str) -> bytes:
        object_key = self._object_key(key)
        try:
            response = self._client.get_object(  # type: ignore[attr-defined]
                Bucket=self._bucket, Key=object_key
            )
            return response["Body"].read()
        except Exception as exc:
            if self._client_error(exc) in {"NoSuchKey", "404", "NoSuchBucket"}:
                raise ObjectNotFound(f"no object is stored under {key}") from exc
            raise InfrastructureFailure(f"object could not be read: {key}") from exc

    def exists(self, key: str) -> bool:
        try:
            object_key = self._object_key(key)
        except ObjectKeyRefused:
            return False
        try:
            self._client.head_object(Bucket=self._bucket, Key=object_key)  # type: ignore[attr-defined]
        except Exception as exc:
            if self._client_error(exc) in {"NoSuchKey", "404", "NotFound"}:
                return False
            raise InfrastructureFailure(f"object could not be read: {key}") from exc
        return True

    def stat(self, key: str) -> StoredObject:
        """Metadata without transferring the payload - except for the hash.

        The bytes are fetched because the hash must describe what is stored.
        S3's `ETag` is not a content hash for a multipart upload and is not
        SHA-256 in any case, so trusting it would record a digest that is not
        the one every other read path checks.
        """
        payload = self.get(key)
        return StoredObject(key=key, sha256=sha256_bytes(payload), size=len(payload))

    def render_location(self, key: str, staging_root: Path) -> Path:
        """Scratch space. The bucket cannot be a render target.

        Keyed by the object key so two concurrent renders cannot collide on one
        scratch file, and rooted in the Workspace temp directory so nothing
        Chromium writes lands in the artifact tree - a stray file there would
        look like an artifact to anything walking it.

        The parent directory is created here, as on the local store: Chromium
        writes to this path directly and cannot create it.
        """
        path = Path(staging_root) / "render" / validate_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def render_cleanup(self, path: Path) -> bool:
        """Always: the payload is in the bucket, this is a leftover copy."""
        try:
            Path(path).unlink()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise InfrastructureFailure(f"render scratch could not be removed: {path}") from exc
        return True

    def ingest(self, key: str, source: Path) -> StoredObject:
        """Upload a renderer-written file, read once.

        Unlike the local store there is no in-place case: the file Chromium
        wrote is never already the stored object, so this always uploads. The
        read that produces the bytes is the read the hash describes.
        """
        resolved = Path(source)
        try:
            payload = resolved.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(f"no file to ingest at {source}") from exc
        except OSError as exc:
            raise InfrastructureFailure(f"object could not be read: {source}") from exc
        return self.put(key, payload)
