"""Delivering the Ready document's PDF, and what a client may be told about its name.

The delivery name is a name, never a location (architecture §6.2:
"Recruiter-friendly names are Content-Disposition/export names, never the
physical identity of an artifact"). `safe_filename` keeps what a person reads -
spaces, punctuation, non-Latin script - and removes only what could make the
name act as a path or as a second header.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ports import ArtifactStream

#: Path separators, control characters, and the characters that would let a
#: filename close its own quoting inside a `Content-Disposition` header. Not an
#: allow-list of letters: the candidate's name may legitimately be Hebrew, and
#: an ASCII allow-list would silently erase it.
_UNSAFE_IN_FILENAME = re.compile(r'[\x00-\x1f\x7f"\\/;,]')


@dataclass(frozen=True)
class DocumentPdfDelivery:
    """The Ready document's PDF, verified present at request time (§16).

    The document's rendered files are mutable working outputs, not registered
    artifacts, so this carries the document's identity and token rather than an
    artifact version. `filename` is the recruiter-facing name, never a location.
    """

    application_id: str
    document_id: str
    document_hash: str
    filename: str
    size: int
    stream: ArtifactStream
    media_type: str = "application/pdf"


def safe_filename(candidate: str, *, fallback: str) -> str:
    """A delivery name that cannot act as a path or as a header.

    Separators are removed rather than the last component being taken, so the
    result cannot carry a "last segment" meaning that some other layer might
    reinterpret. `../../etc/passwd` becomes `etcpasswd`: not a path, and not
    pretending to be a file it is not.
    """
    stripped = _UNSAFE_IN_FILENAME.sub("", candidate).strip().strip(".").strip()
    return stripped or fallback
