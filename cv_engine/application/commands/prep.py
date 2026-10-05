"""CV-preparation commands and results: job text -> analysis -> the one CV document.

These models are deliberately storage-neutral. A client receives identities,
validated domain documents, and workflow state; local paths are resolved only
by an infrastructure adapter.

The mutable CVDocument is named by its Application and guarded by the
`expected_document_hash` the client last read (state-and-use-cases.md §1): a command
that resolved "the current document" for itself could change something the user
never saw.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.validation import ValidationReport
from ...domain.document import ContentCheck, PreparationState
from ._base import BoundaryDTO, DuplicateMatchReason, WriteClient

SOURCE_URL_MAX_CHARACTERS = 2048

#: The document's concurrency token, as every command carries it.
DocumentHash = Field(pattern=r"^[0-9a-f]{64}$")


class IngestCommand(BoundaryDTO):
    company: str
    target_role: str
    job_text: str
    source_url: str | None = None
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient
    acknowledged_duplicates: bool = False


class DuplicateCheckCommand(BoundaryDTO):
    company: str
    target_role: str
    job_text: str
    source_url: str | None = None


#: An exact job text's SHA-256, as an analysis and an edit carry it.
JobTextHash = Field(pattern=r"^[0-9a-f]{64}$")


class UpdateJobTextCommand(BoundaryDTO):
    """Replace the job text the client last read (`expected_job_text_hash`).

    Refused once the Application has a Submission: what was sent stays tied to the
    posting it was sent for.
    """

    application_id: str
    job_text: str
    source_url: str | None = None
    expected_job_text_hash: str = JobTextHash
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class UpdateApplicationNotesCommand(BoundaryDTO):
    application_id: str
    notes: str
    expected_notes: str
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class AnalyzeCommand(BoundaryDTO):
    """§13 `analyze_job`, bound to the exact job text the client read, not to a document."""

    application_id: str
    job_text_hash: str = JobTextHash
    track_override: str | None = None
    profile_override: str | None = None
    emphasis_override: str | None = None
    language_override: str | None = None
    #: Present only when analysis is the write branch of an explicit decision
    #: against an already active context (`apply_analysis_decisions`). A fresh
    #: analysis has no prior analysis or document to compare with.
    expected_analysis_id: str | None = None
    expected_document_hash: str | None = None
    #: Internal flag carried to persistence so an explicit decision is refused
    #: while an Operation that can replace the analysis context is active.
    refuse_matching_context_operation: bool = False
    provider: Literal["openai"] = "openai"
    model: str | None = None
    reasoning_effort: str | None = None


class ApplyAnalysisDecisionsCommand(BoundaryDTO):
    """One local review-form submission (§13).

    Every decision it carries - Track, Profile, language, Emphasis - is
    classification, and a change to any of them creates a new JobAnalysis.
    """

    application_id: str
    job_analysis_id: str
    #: Explicit CAS source copied from the form read. It is deliberately not
    #: inferred from job_analysis_id: naming what to mutate and naming what was
    #: observed are separate claims at an optimistic boundary.
    expected_analysis_id: str
    #: The document the form was read beside; required whenever a document exists.
    expected_document_hash: str | None = None
    track_override: str | None = None
    profile_override: str | None = None
    emphasis_override: str | None = None
    language_override: str | None = None


class BuildFromAnalysisCommand(BoundaryDTO):
    """§14 `build_from_analysis`: re-pin the document to an explicitly named analysis."""

    application_id: str
    analysis_id: str = Field(min_length=1)
    expected_document_hash: str = DocumentHash
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient = "web"


class DraftCommand(BoundaryDTO):
    """§14 `create_draft` against the document the client read.

    Drafting is AI-only: there is no deterministic form to fall back to, so asking
    for it without a configured provider is a refusal.
    """

    application_id: str
    expected_document_hash: str = DocumentHash
    provider: Literal["openai"] = "openai"
    model: str | None = None
    reasoning_effort: str | None = None


class RegenerateSectionCommand(BoundaryDTO):
    """§14 `regenerate_section`: one named section of the document the client read."""

    application_id: str
    expected_document_hash: str = DocumentHash
    section: str
    instruction: str = ""
    model: str | None = None
    reasoning_effort: str | None = None


class RegenerateClaimCommand(BoundaryDTO):
    """§14 `regenerate_claim`: one named claim of the document the client read."""

    application_id: str
    expected_document_hash: str = DocumentHash
    claim_id: str
    instruction: str = ""
    #: Review the user's own wording instead of writing new wording: no writer runs,
    #: and the claim's current text goes to semantic review against its own facts
    #: (product spec §10, the reviewed-evidence path for free-text edits).
    keep_text: bool = False
    model: str | None = None
    reasoning_effort: str | None = None


class ClaimPatch(BoundaryDTO):
    """One claim's new content inside a structured document patch.

    Free text with no fact behind it is not refused here. The domain edit path
    keeps it as a `pending` claim carrying the reason it could not be
    authorized, because §14 requires unauthorized free text to be saved rather
    than silently rejected or discarded.
    """

    claim_id: str
    fact_ids: list[str] = []
    text: str | None = None
    template_id: str | None = None
    template_version: str | None = None


class ClaimAddition(BoundaryDTO):
    """One manually written line to append to a named section.

    It lands `pending` - nothing has authorized it yet - and is resolved the
    same way any other pending line is: linked to a fact, edited into
    something a fact authorizes, or removed.
    """

    section: str
    text: str


class UpdateDocumentCommand(BoundaryDTO):
    """§14 `update_document`: autosave one structured patch against one exact hash."""

    application_id: str
    expected_document_hash: str = DocumentHash
    claim_edits: list[ClaimPatch] = []
    claim_removals: list[str] = []
    claim_additions: list[ClaimAddition] = []
    claim_orders: dict[str, list[str]] = {}

    @model_validator(mode="after")
    def validate_patch(self) -> UpdateDocumentCommand:
        """A patch has to change something, and may not contradict itself."""
        if (
            not self.claim_edits
            and not self.claim_removals
            and not self.claim_additions
            and not self.claim_orders
        ):
            raise ValueError("a document patch must edit, remove, add, or reorder content")
        both = {edit.claim_id for edit in self.claim_edits} & set(self.claim_removals)
        if both:
            raise ValueError(f"a patch cannot both edit and remove the same claim: {sorted(both)}")
        return self


class CheckDocumentCommand(BoundaryDTO):
    """§15 `check_document`: validate the content without approving."""

    application_id: str
    expected_document_hash: str = DocumentHash


class ApproveDocumentCommand(BoundaryDTO):
    """§15 `approve_document`: check and approve in one synchronous action.

    `actor_type` and `client` reach the audit record. Getting them wrong is a
    permanent record saying a person at a terminal approved something a browser did.
    """

    application_id: str
    expected_document_hash: str = DocumentHash
    actor_type: Literal["user", "system"] = "user"
    client: WriteClient


class RenderCommand(BoundaryDTO):
    """§16 `render_document`: render the approved document the client read."""

    application_id: str
    expected_document_hash: str = DocumentHash


class DuplicateMatch(BoundaryDTO):
    application_id: str
    company: str
    target_role: str
    matched_on: list[DuplicateMatchReason]


class IngestedApplication(BoundaryDTO):
    application_id: str
    job_text_hash: str
    warnings: list[str] = []
    duplicate_matches: list[DuplicateMatch] = []


class DuplicateCheckResult(BoundaryDTO):
    matches: list[DuplicateMatch] = []


class UpdatedJobText(BoundaryDTO):
    application_id: str
    job_text_hash: str
    job_text_updated_at: str


class AnalysisResult(BoundaryDTO):
    """One activated JobAnalysis and the document it created, if it created one."""

    application_id: str
    job_text_hash: str
    analysis_id: str
    document_id: str | None = None
    created_document: bool = False
    analysis: JobAnalysis


class AnalysisDecisionsResult(BoundaryDTO):
    """The new analysis produced by a review-form classification decision.

    The document is not re-pinned; `document_hash` is its current token.
    """

    application_id: str
    job_analysis_id: str
    analysis: JobAnalysis
    document_id: str | None = None
    document_hash: str | None = None


class DocumentMutationResult(BoundaryDTO):
    """What a synchronous document change returns: the new token and state."""

    application_id: str
    document_id: str
    document_hash: str
    preparation_state: PreparationState
    content_check: ContentCheck
    #: Claims this change saved as pending, so a client need not diff to find them.
    pending_claim_ids: list[str] = []


class DocumentCheckResult(DocumentMutationResult):
    """`check` and `approve`. A failed check is data, not an exception (§22)."""

    passed: bool
    report: ValidationReport
    approved_at: str | None = None


class DraftResult(BoundaryDTO):
    application_id: str
    document_id: str
    document_hash: str


class RegenerationResult(BoundaryDTO):
    """What one AI regeneration committed, and the evidence that produced it."""

    application_id: str
    document_id: str
    document_hash: str
    regenerated_claim_ids: list[str]
    ai_call_id: str


class RenderResult(BoundaryDTO):
    application_id: str
    document_id: str
    document_hash: str
    validation: ValidationReport


class UpdatedApplicationNotes(BoundaryDTO):
    application_id: str
    notes: str
    updated_at: str


class DecisionMarkdownExport(BoundaryDTO):
    application_id: str
    document_id: str
    filename: str
    content: str
    content_hash: str
