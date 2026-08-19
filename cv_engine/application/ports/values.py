"""Values passed across a port boundary.

Frozen because a port hands them between layers: a mutable payload would let
the receiving side change what the caller believes it sent.
"""

from __future__ import annotations

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
