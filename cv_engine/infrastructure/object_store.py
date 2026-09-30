from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..application.errors import InfrastructureFailure
from ..util import sha256_bytes
from .paths import is_regular_file_within, resolve_within


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
    """Keys and bytes. No `Path`, no directories, no temp staging, no delete.

    There is no delete on purpose: every object is an immutable payload, and a
    store that cannot remove one cannot race a registration that references it
    (architecture.md §7.1).

    The unit is a whole payload, because every immutable payload in this system
    is one document that the system produced itself - a CV, a
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

    def keys_under(self, prefix: str, *, modified_before: datetime | None = None) -> Iterator[str]:
        """Enumerate stored keys beneath a prefix without changing any payload.

        Empty prefix inventories the whole store. Listing is observational:
        concurrent writers may add objects while enumeration is in progress.
        `modified_before` keeps only objects last written before that instant,
        which is how orphan reclaim leaves a write that has not registered yet
        alone (architecture.md §7.1).
        """
        ...

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

    def keys_under(self, prefix: str, *, modified_before: datetime | None = None) -> Iterator[str]:
        """Every key stored beneath `prefix`, in sorted order.

        Only regular contained files are listed; symlinked directories and
        files are excluded from inspection.
        """
        base = resolve_within(self._root, validate_key(prefix)) if prefix else self._root
        if not base.is_dir():
            return
        cutoff = None if modified_before is None else modified_before.timestamp()
        for path in sorted(base.rglob("*")):
            if not is_regular_file_within(self._root, path):
                continue
            if cutoff is not None and path.stat().st_mtime >= cutoff:
                continue
            yield path.relative_to(self._root).as_posix()


def _aware(moment: datetime) -> datetime:
    """boto3 returns aware datetimes; a naive one is read as UTC rather than local time."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


class S3ObjectStore:
    """`ObjectStore` over an S3-compatible bucket. R2 via `endpoint_url`.

    boto3 is imported inside `__init__` rather than at module scope, because
    the local path must keep working with no cloud SDK installed, and a
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
            # The optional s3 extra may be absent when using local storage.
            import boto3  # pyright: ignore[reportMissingImports]
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

    def keys_under(self, prefix: str, *, modified_before: datetime | None = None) -> Iterator[str]:
        requested = validate_key(prefix) if prefix else ""
        bucket_prefix = f"{self._prefix}/" if self._prefix else ""
        query_prefix = f"{bucket_prefix}{requested}/" if requested else bucket_prefix
        continuation: str | None = None
        while True:
            arguments = {"Bucket": self._bucket, "Prefix": query_prefix}
            if continuation is not None:
                arguments["ContinuationToken"] = continuation
            try:
                response = self._client.list_objects_v2(**arguments)  # type: ignore[attr-defined]
            except Exception as exc:
                raise InfrastructureFailure("object inventory could not be read") from exc
            for row in response.get("Contents", []):
                key = row["Key"]
                if not key.startswith(query_prefix) or key.endswith("/"):
                    continue
                if modified_before is not None and _aware(row["LastModified"]) >= modified_before:
                    continue
                yield validate_key(key[len(bucket_prefix) :])
            if not response.get("IsTruncated", False):
                return
            next_token = response.get("NextContinuationToken")
            if not next_token or next_token == continuation:
                raise InfrastructureFailure("object inventory pagination did not advance")
            continuation = next_token
