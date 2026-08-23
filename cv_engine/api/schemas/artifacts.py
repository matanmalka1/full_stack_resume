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

from typing import Any

from .applications import ArtifactVersionResponse
from .health import HttpSchema


class RenderRevisionRequest(HttpSchema):
    """The Application the client believes it is rendering for.

    Explicit rather than inferred from the revision, for the same reason
    `apply-decisions` states it: a client that names both is telling the server
    what it believes, and a mismatch is a `412` naming the broken lineage
    instead of a render landing on another Application's revision.
    """

    application_id: str


class ArtifactVersionDetailResponse(ArtifactVersionResponse):
    """Registered metadata plus verified download eligibility (§20)."""

    downloadable: bool
    size: int | None = None
    unavailable_reason: str | None = None


class ApprovedRevisionResponse(HttpSchema):
    """One immutable ApprovedRevision and its re-derived Ready qualification.

    `ready_qualified` is a property of this revision's own stored evidence.
    Whether it is the *active* Ready milestone is `preparation_state` on
    `GET /applications/{id}`, and the two are separate on purpose: a revision
    stays qualified and downloadable after a newer JobSnapshot has moved the
    Application off it.
    """

    id: str
    application_id: str
    version_number: int
    working_draft_id: str
    job_snapshot_id: str
    job_analysis_id: str
    selection_plan_id: str
    validation_run_id: str
    draft_edit_version: int
    draft_content_hash: str
    facts_version: str
    approved_at: str
    decision_provenance: dict[str, Any]
    ready_qualified: bool
    pdf_artifact_version_id: str | None = None
    # `dict`, matching `ValidationRunResponse.report`: reports are one shape
    # across the API, and giving this one a typed model would make two.
    ready_validation: dict[str, Any]
