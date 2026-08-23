"""Values passed across a port boundary.

Frozen because a port hands them between layers: a mutable payload would let
the receiving side change what the caller believes it sent.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DraftPaths:
    """Where one draft's two payloads ended up."""

    markdown: Path
    manifest: Path


@dataclass(frozen=True)
class StoredDraft:
    """A draft as it was stored, with the exact document text that was written.

    The text travels with the locations so a caller can validate what is stored
    without reading it back, and cannot accidentally validate something else.
    """

    paths: DraftPaths
    markdown: str


@dataclass(frozen=True)
class SnapshotPayload:
    """Storage-neutral metadata for one immutable JobSnapshot payload."""

    reference: str
    sha256: str
    size: int


@dataclass(frozen=True)
class RevisionPayloads:
    """The two verified immutable payloads owned by one ApprovedRevision."""

    structured: SnapshotPayload
    markdown: SnapshotPayload


@dataclass(frozen=True)
class RenderTargets:
    """Where one approved version's rendered outputs belong."""

    html: Path
    pdf: Path
    screenshot: Path
    recruiter_pdf_filename: str


@dataclass(frozen=True)
class ArtifactStream:
    """One verified immutable payload, as bytes rather than as a location.

    Deliberately carries no `Path`. A download is the one place where a local
    filesystem location would otherwise travel outward through the application
    layer and into an HTTP response, and architecture §14 requires that no
    endpoint accept or expose one. The store has already resolved containment
    and re-checked the registered hash by the time this exists; what is left is
    the bytes and how many of them there are.

    The bytes are already captured and already verified: `size` and the content
    hash the caller checked describe *these* bytes, not a file that will be
    reopened later. A descriptor that reread its path on iteration would leave a
    time-of-check/time-of-use window in which a substituted payload is delivered
    under the previous hash and length.

    `chunks` is a factory rather than an iterator so the descriptor can be
    built, inspected, and handed on before anything is consumed, and so it can
    be iterated more than once without changing what it yields.
    """

    size: int
    chunks: Callable[[], Iterator[bytes]]


@dataclass(frozen=True)
class TaskContract:
    """One AI task's declared identity, as the contract file states it."""

    name: str
    version: str
    input: str
    input_schema_version: str
    output: str
    output_schema_version: str
    critical_state: bool
    model: str | None = None


@dataclass(frozen=True)
class TaskContracts:
    """The single source for contract version, prompt version, and prompt text.

    `ai/contracts/task_contracts.json` and the prompt it names are Knowledge
    files (architecture §6.3), so they load through the Knowledge port like
    every other version-controlled input. Before Stage G the same two strings
    were typed into the provider adapter and into the deterministic
    generation-run record while the file was read by nothing: three places that
    could disagree about what ran. There is now one.

    `prompt_hash` is the exact identity. The version is the label a human
    reads; the hash is what proves which bytes the provider was given.
    """

    version: str
    prompt_version: str
    prompt_hash: str
    prompt_text: str
    tasks: Mapping[str, TaskContract]

    def get(self, name: str) -> TaskContract:
        try:
            return self.tasks[name]
        except KeyError as exc:
            raise KeyError(f"no task contract is declared for {name}") from exc
