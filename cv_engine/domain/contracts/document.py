"""The one mutable CV document per Application, and the Submission that freezes it.

state-and-use-cases.md §3 and §18. The document stores three stamps of its basis; the
basis itself is computed on read (`cv_engine.domain.document`), so nothing here can say
whether the document is approved or ready without the Knowledge it depends on.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import StrictModel
from .drafts import DraftDocument
from .validation import ValidationReport

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class BuiltWith(StrictModel):
    """The Profile version the document was built with.

    Drives the PROFILE_CHANGED warning only: every gate validates against the current
    version, never against this.
    """

    profile_version: str = Field(min_length=1)


class CVDocument(StrictModel):
    id: str
    application_id: str
    analysis_id: str
    content: DraftDocument | None = None
    built_with: BuiltWith
    document_hash: Sha256
    content_report: ValidationReport | None = None
    checked_basis: Sha256 | None = None
    passed: bool | None = None
    approved_basis: Sha256 | None = None
    approved_at: str | None = None
    rendered_basis: Sha256 | None = None
    html_path: str | None = None
    pdf_path: str | None = None
    #: The structured failure reason of the newest failed render whose expected
    #: document hash still equalled `document_hash` (§16).
    last_render_error: dict[str, Any] | None = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def stamps_are_paired(self) -> CVDocument:
        check = (self.content_report is None, self.checked_basis is None, self.passed is None)
        if len(set(check)) != 1:
            raise ValueError("content_report, checked_basis and passed are set together")
        if self.content_report is not None and self.content_report.passed != self.passed:
            raise ValueError("passed must restate the stored content report")
        if (self.approved_basis is None) != (self.approved_at is None):
            raise ValueError("approved_basis and approved_at are set together")
        render = (self.rendered_basis is None, self.html_path is None, self.pdf_path is None)
        if len(set(render)) != 1:
            raise ValueError("rendered_basis, html_path and pdf_path are set together")
        if self.content is None and not (
            self.checked_basis is None
            and self.approved_basis is None
            and self.rendered_basis is None
            and self.last_render_error is None
        ):
            raise ValueError("a document without content carries no stamps")
        if self.last_render_error is not None and "code" not in self.last_render_error:
            raise ValueError("last_render_error must carry a failure code")
        return self


class DocumentSubmission(StrictModel):
    """An immutable record of a send that already happened (§18).

    Internal submissions copy what was sent; external ones carry none of it.
    """

    id: str
    application_id: str
    submission_type: Literal["internal", "external"]
    #: The Application's job text when this was sent; it locks from then on.
    job_text_hash: Sha256 | None = None
    document_hash: Sha256 | None = None
    content: DraftDocument | None = None
    html_path: str | None = None
    html_sha256: Sha256 | None = None
    pdf_path: str | None = None
    pdf_sha256: Sha256 | None = None
    submitted_at: str
    metadata: dict[str, Any] = {}

    @model_validator(mode="after")
    def references_match_type(self) -> DocumentSubmission:
        references = (
            self.job_text_hash,
            self.document_hash,
            self.content,
            self.html_path,
            self.html_sha256,
            self.pdf_path,
            self.pdf_sha256,
        )
        if self.submission_type == "internal" and any(value is None for value in references):
            raise ValueError("an internal submission records the content and files it sent")
        if self.submission_type == "external" and any(value is not None for value in references):
            raise ValueError("an external submission carries no document content or files")
        return self
