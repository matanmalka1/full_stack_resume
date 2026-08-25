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
