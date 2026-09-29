"""The one CV document per Application over HTTP (state-and-use-cases.md §14–§16, §21).

The document's `document_hash` is its concurrency token. A read returns it as the
ETag; the autosave `PATCH` takes it as `If-Match`, and every action carries it in the
body as `expected_document_hash`: an action on a resource is not a conditional replacement of it, and an action that
accepted `If-Match: *` would be the lost update the token exists to prevent.

Nothing here carries a filesystem path.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ...domain.contracts.selection import OmissionReason, ProposalSource, SelectionOutcome
from ...domain.contracts.taxonomy import Emphasis
from ...domain.document import ContentCheck, PreparationState
from .drafts import (
    ContentPatchRequest,
    DraftFactResponse,
    DraftOutlineResponse,
    ValidationReportResponse,
)
from .health import HttpSchema

Sha256 = Field(pattern=r"^[0-9a-f]{64}$")


class DocumentActionRequest(HttpSchema):
    """The document the client was looking at when the user acted."""

    expected_document_hash: str = Sha256


class UpdateDocumentRequest(ContentPatchRequest):
    """What `PATCH /applications/{id}/document` applies as one edit (§14).

    The token is `If-Match`, not a body field.
    """


class UpdateSelectionRequest(DocumentActionRequest):
    """A deterministic selection change (§14 `update_selection`).

    Two lists, not three: explicit inclusion is a pin, and what ends up selected is a
    response field. `emphasis_override` null means "leave the effective Emphasis as it
    is", not "clear the override".
    """

    pinned_fact_ids: list[str] = []
    excluded_fact_ids: list[str] = []
    emphasis_override: Emphasis | None = None


class ProposeSelectionRequest(DocumentActionRequest):
    provider: Literal["openai"] = "openai"


class BuildFromAnalysisRequest(DocumentActionRequest):
    """Re-pin the document to an explicitly named analysis (§14 `build_from_analysis`)."""

    analysis_id: str = Field(min_length=1)


class CreateDraftRequest(DocumentActionRequest):
    provider: Literal["deterministic", "openai"] = "deterministic"


class RegenerateDocumentSectionRequest(DocumentActionRequest):
    section: str = Field(max_length=200)
    instruction: str = Field(default="", max_length=2000)


class RegenerateDocumentClaimRequest(DocumentActionRequest):
    claim_id: str = Field(max_length=200)
    instruction: str = Field(default="", max_length=2000)
    keep_text: bool = Field(
        default=False,
        description=(
            "Keep the claim's current wording and only run semantic review of it against "
            "its own linked facts. The claim must be pending and linked to at least one fact."
        ),
    )


class BuiltWithResponse(HttpSchema):
    profile_version: str
    selection_policy_version: str


class DocumentCandidateResponse(HttpSchema):
    fact_id: str
    text: str | None = None
    section: str
    outcome: SelectionOutcome
    reason: OmissionReason | None = None
    user_selectable: bool


class DocumentSelectionResponse(HttpSchema):
    """The selection with its candidate accounting (§20)."""

    emphasis: Emphasis
    emphasis_override: Emphasis | None = None
    selected_fact_ids: list[str]
    pinned_fact_ids: list[str]
    excluded_fact_ids: list[str]
    #: Null for engine and user selections.
    proposed_by: ProposalSource | None = None
    proposal_rationale: str | None = None
    candidates: list[DocumentCandidateResponse]


class DocumentResponse(HttpSchema):
    """`GET /applications/{id}/document`. `document_hash` is also the ETag."""

    id: str
    application_id: str
    analysis_id: str
    document_hash: str
    built_with: BuiltWithResponse
    language: str
    selection: DocumentSelectionResponse
    #: The DraftDocument as the versioned domain document; null until generated.
    content: dict[str, Any] | None = None
    outline: DraftOutlineResponse | None = None
    facts: list[DraftFactResponse] = []
    preparation_state: PreparationState
    content_check: ContentCheck
    #: The stored report, returned even when outdated so it can be shown as such.
    content_report: ValidationReportResponse | None = None
    approved_at: str | None = None
    last_render_error: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class DocumentMutationResponse(HttpSchema):
    """What a synchronous document change returns: the new token and state."""

    application_id: str
    document_id: str
    document_hash: str
    preparation_state: PreparationState
    content_check: ContentCheck
    pending_claim_ids: list[str] = []


class DocumentCheckResponse(DocumentMutationResponse):
    """`check` and `approve`. A failed check is `200` with `passed=false` (§22)."""

    passed: bool
    report: ValidationReportResponse
    approved_at: str | None = None


class DecisionExportResponse(HttpSchema):
    application_id: str
    document_id: str
    markdown: str
