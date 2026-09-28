"""Artifact, render, and Ready representations.

Every schema here is addressed by ID. None of them carries a filesystem
location, and the architecture test that reads the generated OpenAPI is what
keeps it that way rather than this docstring.

The download response is deliberately absent: a download is a byte stream with
a `Content-Disposition`, not a JSON body, so it has no model. What it *does*
have is a declared media type in the route, so the generated TypeScript knows
it is not receiving JSON.
"""

from __future__ import annotations

from .applications import ArtifactVersionResponse


class ArtifactVersionDetailResponse(ArtifactVersionResponse):
    """Registered metadata plus verified download eligibility (§20)."""

    downloadable: bool
    size: int | None = None
    unavailable_reason: str | None = None
