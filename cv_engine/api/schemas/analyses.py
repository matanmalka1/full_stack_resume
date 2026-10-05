"""Analysis and review decisions over HTTP.

`analysis` is carried as an object rather than restated field by
field, the same way `JobAnalysisResponse` already carries one. They are domain
documents with their own versioned schema; a second hand-written copy of that
schema in the HTTP layer could only drift from it, and a router that named the
domain types directly would be a router doing domain work.

The classification *overrides* are the opposite case and are typed. A closed
vocabulary of four string sets is not a versioned document being restated: it
is the constraint the request is already subject to, enforced today only after
the value has left this layer. Flattened to `str` it cost twice - the generated
TypeScript was `string`, so a client had to keep its own copy of the sets, and
a value outside them reached `ProfileName(...)` as a bare `ValueError` and
surfaced to the user as a 500. Naming the enums here refuses it as a 422 before
a command is built. The architecture rule allows `domain` inside `api` and
forbids it inside `routers/`, which is where a domain type would mean a router
doing domain work; these are schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ...domain.contracts.analysis import Language
from ...domain.contracts.taxonomy import (
    Emphasis,
    ProfileName,
    Track,
)
from .applications import ApplicationStateResponse
from .health import HttpSchema


class ClassificationOverrides(HttpSchema):
    """The four explicit matching decisions accepted by analysis forms.

    Shared because both requests that accept them accept exactly the same four,
    and a second declaration is a second place to forget one.

    Every field is optional and withholding one is not a retraction. Any changed
    value creates a new immutable JobAnalysis; the document is not re-pinned.
    """

    track_override: Track | None = None
    profile_override: ProfileName | None = None
    emphasis_override: Emphasis | None = None
    language_override: Language | None = None


class CreateAnalysisRequest(ClassificationOverrides):
    """What `POST /applications/{id}/analyses` accepts.

    `job_text_hash` is explicit: an analyze command that picked up whatever text is
    current could classify something other than what the user was looking at.
    """

    job_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: Literal["openai"] = "openai"


class ApplyAnalysisDecisionsRequest(ClassificationOverrides):
    """One review-form submission (§13).

    Every decision it carries - Track, Profile, language, Emphasis - is
    classification, and a change to any of them creates a new JobAnalysis.
    """

    application_id: str
    #: The active analysis shown by the form. Required separately from the path
    #: identity so the write can compare the observation as well as resolve the
    #: immutable source being addressed.
    expected_analysis_id: str
    #: The document the form was read beside; required whenever a document exists.
    #: A decision made against a document that has since moved is refused rather
    #: than applied to one the user never saw.
    expected_document_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AnalysisDecisionsResponse(HttpSchema):
    """The new analysis created by the decision.

    `job_analysis_id` names the analysis the client should work from now, the new
    one every decision creates. The decision never re-pins the document;
    `document_hash` is its token now.
    """

    application_id: str
    job_analysis_id: str
    analysis: dict[str, Any]
    document_id: str | None = None
    document_hash: str | None = None
    #: Fresh authoritative projection after the decision. Clients choose the next
    #: step from this rather than predicting what the new context allows.
    state: ApplicationStateResponse
