"""Delivering one registered artifact, and what a client is allowed to learn.

A free-function module taking ports, the way `ready.py` is one. Two services
need these rules - `RenderingService` to hand a payload out, and
`ApplicationQueryService` to say whether one could be handed out - and a rule
that lived in one of them would be reimplemented in the other.

Three decisions are recorded here because each is a contract rather than an
implementation detail:

1. **The media type comes from the registered `artifact_type`, never from the
   filename.** The type is a value this system wrote into the database when it
   produced the payload; the extension is part of a stored string. Serving a
   PDF as HTML because a row's path ended in `.html` is exactly the confusion
   that a registry exists to prevent.
2. **The delivery name is a name, never a location** (architecture §6.2:
   "Recruiter-friendly names are Content-Disposition/export names, never the
   physical identity of an artifact"). `safe_filename` keeps what a person
   reads - spaces, punctuation, non-Latin script - and removes only what could
   make the name act as a path or as a second header.
3. **Nothing here returns a `Path`.** The verification that a payload is
   contained, present, and unchanged happens behind the port; what crosses back
   is an `ArtifactStream` whose bytes are the bytes that were hashed, so the
   `ETag` and `Content-Length` a router derives from it cannot describe content
   the client is not about to receive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ApplicationError
from .ports import ArtifactStream, SnapshotPayloadStore
from .queries import ArtifactVersionView

#: Registered artifact type -> what a client should be told it is receiving.
#: Every type this system registers appears here; an unregistered type falls
#: back to the octet stream rather than being guessed at from its path.
ARTIFACT_MEDIA_TYPES: dict[str, str] = {
    "resume_pdf": "application/pdf",
    "resume_html": "text/html; charset=utf-8",
    "resume_markdown": "text/markdown; charset=utf-8",
    "visual_evidence": "image/png",
    "claim_manifest": "application/json",
    "working_draft_snapshot": "application/json",
    "job_snapshot": "text/plain; charset=utf-8",
    "provider_response": "application/json",
}

DEFAULT_MEDIA_TYPE = "application/octet-stream"

#: Suffix for the fallback delivery name, per media type rather than per
#: artifact type, so a new artifact type that reuses a media type gets a
#: sensible extension without a second table to keep in step.
_MEDIA_TYPE_SUFFIXES: dict[str, str] = {
    "application/pdf": ".pdf",
    "text/html; charset=utf-8": ".html",
    "text/markdown; charset=utf-8": ".md",
    "image/png": ".png",
    "application/json": ".json",
    "text/plain; charset=utf-8": ".txt",
    DEFAULT_MEDIA_TYPE: "",
}

#: Path separators, control characters, and the characters that would let a
#: filename close its own quoting inside a `Content-Disposition` header. Not an
#: allow-list of letters: the candidate's name may legitimately be Hebrew, and
#: an ASCII allow-list would silently erase it.
_UNSAFE_IN_FILENAME = re.compile(r'[\x00-\x1f\x7f"\\/;,]')


@dataclass(frozen=True)
class ArtifactDelivery:
    """One registered artifact, verified and ready to be handed to a client.

    Not a `BoundaryDTO`: it carries bytes rather than a serialisable value, and
    the whole point of the type is what it does *not* carry, which is anywhere
    the bytes came from.
    """

    artifact_version_id: str
    artifact_type: str
    content_hash: str
    media_type: str
    filename: str
    size: int
    stream: ArtifactStream


@dataclass(frozen=True)
class ArtifactAvailability:
    """Whether one registered artifact could be downloaded right now.

    `reason` is the refusal's stable `code` when it could not, so a client can
    say why a download is unavailable without being told a path.
    """

    downloadable: bool
    size: int | None = None
    reason: str | None = None


def safe_filename(candidate: str, *, fallback: str) -> str:
    """A delivery name that cannot act as a path or as a header.

    Separators are removed rather than the last component being taken, so the
    result cannot carry a "last segment" meaning that some other layer might
    reinterpret. `../../etc/passwd` becomes `etcpasswd`: not a path, and not
    pretending to be a file it is not.
    """
    stripped = _UNSAFE_IN_FILENAME.sub("", candidate).strip().strip(".").strip()
    return stripped or fallback


def media_type_for(artifact_type: str) -> str:
    return ARTIFACT_MEDIA_TYPES.get(artifact_type, DEFAULT_MEDIA_TYPE)


def default_filename(artifact_version_id: str, artifact_type: str) -> str:
    """The delivery name for an artifact that carries no friendly one.

    Built from the registered type and a short prefix of the version ID, so it
    is recognisable and unique without repeating the stored layout.
    """
    suffix = _MEDIA_TYPE_SUFFIXES.get(media_type_for(artifact_type), "")
    return f"{artifact_type}-{artifact_version_id[:8]}{suffix}"


def registered_filename(view: ArtifactVersionView) -> str | None:
    """The friendly name the registration recorded, if it recorded one.

    Only the rendered PDF has one today; it is written at render time from the
    normalized role and the candidate context, and it is the name a recruiter
    is meant to see.
    """
    name = view.metadata.get("recruiter_filename")
    return name if isinstance(name, str) and name else None


def deliver_artifact(
    payloads: SnapshotPayloadStore,
    view: ArtifactVersionView,
    stored_path: str,
    *,
    filename: str | None = None,
) -> ArtifactDelivery:
    """Verify one registered artifact through the port and describe the result.

    The stored path is passed beside the view rather than inside it, which is
    the point: `ArtifactVersionView` is the projection a client receives and it
    has never carried a path. Keeping the two separate means the only code that
    handles a location is the argument this function forwards to the port.

    Every refusal comes from the store, which is the only place that knows
    which check failed. Nothing is caught and re-raised here: doing so would
    mean writing a second message for a condition this layer did not observe.
    """
    stream = payloads.open_artifact(stored_path, view.content_hash)
    candidate = filename or registered_filename(view)
    fallback = default_filename(view.id, view.artifact_type)
    return ArtifactDelivery(
        artifact_version_id=view.id,
        artifact_type=view.artifact_type,
        content_hash=view.content_hash,
        media_type=media_type_for(view.artifact_type),
        filename=safe_filename(candidate, fallback=fallback) if candidate else fallback,
        size=stream.size,
        stream=stream,
    )


def verify_artifact(
    payloads: SnapshotPayloadStore,
    view: ArtifactVersionView,
    stored_path: str,
) -> ArtifactAvailability:
    """Whether this registered artifact would download, without downloading it.

    The metadata endpoint answers "can this be fetched", and the honest answer
    runs the same verification the fetch would: a client told a payload is
    available and then refused at download learned nothing from the first call.
    A refusal is reported as its stable `code`, never as its message, because
    the message is where a path would be if one ever appeared.
    """
    try:
        stream = payloads.open_artifact(stored_path, view.content_hash)
    except ApplicationError as exc:
        return ArtifactAvailability(downloadable=False, reason=exc.code)
    return ArtifactAvailability(downloadable=True, size=stream.size)
