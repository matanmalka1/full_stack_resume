"""Delivering the Ready document's PDF.

The delivery name is a name, never a location (architecture §6.2:
"Recruiter-friendly names are Content-Disposition/export names, never the
physical identity of an artifact").
"""

from __future__ import annotations

from dataclasses import dataclass

from .ports import ArtifactStream


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
