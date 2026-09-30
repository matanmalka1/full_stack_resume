"""The document's content, its editable outline, and its content report over HTTP.

The content itself travels as an object, for the same reason the analysis does
in `schemas/analyses.py`: it is a versioned domain document, and a second hand-written copy of its schema in the HTTP layer could
only drift from the one that is enforced.

Nothing here carries a filesystem path, and nothing here carries the ETag. The
token is a header, which is what makes it usable by a conditional request.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from ...domain.contracts.drafts import (
    ClaimStyle,
    ClaimType,
)
from .health import HttpSchema


class ClaimPatchRequest(HttpSchema):
    """One claim's replacement content.

    Free text with no fact behind it is accepted and saved as a pending claim
    carrying the reason it could not be authorized; it is never discarded.
    """

    claim_id: str
    fact_ids: list[str] = []
    text: str | None = None
    template_id: str | None = None
    template_version: str | None = None


class ClaimAdditionRequest(HttpSchema):
    """One manually written line to append to a named section.

    It is saved as a `pending` claim, exactly like free text an edit could not
    authorize: resolved by linking it to a fact, editing it into wording a
    fact does authorize, or removing it.
    """

    section: str = Field(max_length=200)
    text: str = Field(max_length=2000)


class ContentPatchRequest(HttpSchema):
    """The structured patch `PATCH /applications/{id}/document` applies as one edit.

    Removals travel with the edits rather than in a command of their own.
    Product spec §10 makes removal one of the three resolutions for free text
    nothing could authorize, and §14 commits an autosave patch as a single edit
    against a single expected version - a second command would need its own
    token and could interleave with the save already in flight.

    At least one content operation has to be present. Reordering uses complete
    permutations, so an omitted order means "leave this structure alone" while
    an empty order is meaningful only for an already empty section. Only claims
    within a section reorder: section order is Profile policy (product spec §10),
    so the patch has no field that could move a section.
    """

    claim_edits: list[ClaimPatchRequest] = []
    claim_removals: list[str] = Field(
        default=[],
        description=(
            "Section claims to delete outright. Headlines, contacts, role headings, "
            "and dates are structural and cannot be removed."
        ),
    )
    claim_additions: list[ClaimAdditionRequest] = []
    claim_orders: dict[str, list[str]] = Field(
        default={},
        description="Complete claim-ID order for each named section being reordered.",
    )

    @model_validator(mode="after")
    def validate_patch(self) -> ContentPatchRequest:
        """Refused as a bad request, before any of it is applied.

        The command carries the same invariant, but a contradiction
        that only surfaced there would reach the client as a 500 rather than as
        the `422` an unusable request deserves.
        """
        if (
            not self.claim_edits
            and not self.claim_removals
            and not self.claim_additions
            and not self.claim_orders
        ):
            raise ValueError("a patch must edit, remove, add, or reorder content")
        both = {edit.claim_id for edit in self.claim_edits} & set(self.claim_removals)
        if both:
            raise ValueError(f"a patch cannot both edit and remove the same claim: {sorted(both)}")
        return self


class ClaimReviewAssertionResponse(HttpSchema):
    claim_quote: str
    fact_ids: list[str]
    source_quotes: list[str]


class ClaimReviewEvidenceResponse(HttpSchema):
    """User-facing proof excerpts, without provider artifact IDs or input hashes."""

    policy_version: str
    assertions: list[ClaimReviewAssertionResponse]


class DraftClaimResponse(HttpSchema):
    """One editable line: what a claim edit addresses, plus what it currently is.

    `claim_type` and `style` are the domain's closed sets rather than `str`, so
    a client's status labels stay exhaustive over them and a claim type added
    here fails that client's build instead of reaching a screen untranslated.
    """

    claim_id: str
    style: ClaimStyle
    text: str
    claim_type: ClaimType
    fact_ids: list[str]
    pending_reason: str | None = None
    review_evidence: ClaimReviewEvidenceResponse | None = None


class DraftSectionResponse(HttpSchema):
    name: str
    claims: list[DraftClaimResponse]


class DraftOutlineResponse(HttpSchema):
    """The document's editable structure, derived from `content` on every read.

    Not a competing copy of the content: it stores nothing, it is computed from
    the same object `content` carries, and it holds only what an edit can
    address. `content` remains the whole versioned document for anything that
    needs more than the editor does.
    """

    headline: DraftClaimResponse
    contacts: list[DraftClaimResponse]
    sections: list[DraftSectionResponse]


class DraftFactResponse(HttpSchema):
    """One fact the content's claims link.

    `text` is nullable: a fact the store can no longer resolve is already
    reported as a review reason by the state projection, and a read that raised
    over it would turn an explainable staleness into a `500`. `section` is the
    content section whose claims first link it, null for the headline and contacts.
    """

    fact_id: str
    text: str | None = None
    linked_claim_ids: list[str] = []
    section: str | None = None


class ValidationIssueResponse(HttpSchema):
    group: str
    code: str
    message: str
    hard: bool


class ValidationReportResponse(HttpSchema):
    report_schema_version: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    passed: bool
    groups: dict[str, bool]
    issues: list[ValidationIssueResponse]
    evidence: dict[str, Any]
