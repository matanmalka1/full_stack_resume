from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..util import normalized_text
from .candidate import contact_href
from .contracts.drafts import DraftDocument
from .contracts.knowledge import CandidateContext, Profile, filing_role
from .contracts.validation import ValidationIssue, ValidationReport
from .date_display import displayed_claim_text

RENDER_VALIDATION_GROUPS = (
    "render",
    "page_count",
    "pdf",
    "ats",
    "links",
    "visual",
    "direction",
    "filename",
)


@dataclass(frozen=True, slots=True)
class RenderGeometry:
    scroll_width: int | float
    client_width: int | float
    scroll_height: int | float
    client_height: int | float
    offenders: list[str]
    direction: str | None
    links: list[str]
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RenderEvidence:
    html_path: str
    html_exists: bool
    html_size: int
    html_text: str
    pdf_path: str
    pdf_name: str
    pdf_exists: bool
    pdf_size: int
    pdf_error: str | None
    page_count: int
    extracted_text: str
    pdf_sha256: str | None
    geometry: RenderGeometry


def page_limit(profile: Profile) -> int:
    """How many pages a CV built for `profile` may run to."""
    return 2 if profile.allow_two_pages else 1


def normalized_role_filename(role: str, candidate: CandidateContext) -> str:
    """The delivered PDF's filename. A Profile refuses a role that cleans to nothing."""
    cleaned = filing_role(role)
    if not cleaned:
        raise ValueError(f"role {role!r} leaves no filename once cleaned")
    return f"{candidate.resolved_filename_name} - {cleaned} - CV.pdf"


def validate_render_evidence(
    draft: DraftDocument,
    profile: Profile,
    evidence: RenderEvidence,
    candidate: CandidateContext,
) -> ValidationReport:
    groups: dict[str, bool] = dict.fromkeys(RENDER_VALIDATION_GROUPS, True)
    issues: list[ValidationIssue] = []
    if not evidence.html_exists or evidence.html_size == 0:
        groups["render"] = False
        issues.append(
            ValidationIssue(group="render", code="html-missing", message=evidence.html_path)
        )
    if not evidence.pdf_exists or evidence.pdf_size == 0:
        groups["pdf"] = False
        issues.append(ValidationIssue(group="pdf", code="pdf-missing", message=evidence.pdf_path))
        return ValidationReport.from_findings(groups=groups, issues=issues)

    if evidence.pdf_error is not None:
        groups["pdf"] = False
        issues.append(ValidationIssue(group="pdf", code="pdf-corrupt", message=evidence.pdf_error))

    maximum = page_limit(profile)
    if evidence.page_count < 1 or evidence.page_count > maximum:
        groups["page_count"] = False
        issues.append(
            ValidationIssue(
                group="page_count",
                code="page-count",
                message=f"{evidence.page_count} pages; maximum {maximum}",
            )
        )

    # A claim is looked for as it is displayed: a Hebrew date line shows its numeric
    # form, never the month names its claim holds (see `date_display`).
    section_claims = [claim for section in draft.sections for claim in section.claims]
    claim_texts = [draft.headline.text, *(claim.text for claim in draft.contacts)]
    claim_texts.extend(
        displayed_claim_text(claim.style, claim.text, draft.language) for claim in section_claims
    )
    normalized_pdf = normalized_text(evidence.extracted_text)
    found = sum(
        _claim_recoverable(text, normalized_pdf, draft.language == "he") for text in claim_texts
    )
    coverage = found / len(claim_texts) if claim_texts else 0
    if coverage < 0.9:
        groups["ats"] = False
        issues.append(
            ValidationIssue(
                group="ats",
                code="text-coverage",
                message=f"PDF text coverage is {coverage:.1%}",
            )
        )

    # Coverage tolerates bidi reordering, which is right for prose and fatal for a
    # date range: an ATS reads experience from the range as one run. Each date line
    # must be extracted whole, differing at most in whitespace.
    compact_pdf = _without_whitespace(normalized_pdf)
    dates = [
        displayed_claim_text(claim.style, claim.text, draft.language)
        for claim in section_claims
        if claim.style == "date"
    ]
    broken_dates = [
        date for date in dates if _without_whitespace(normalized_text(date)) not in compact_pdf
    ]
    if broken_dates:
        groups["ats"] = False
        issues.append(
            ValidationIssue(
                group="ats",
                code="date-range",
                message="Dates not extracted as one run: " + "; ".join(broken_dates),
            )
        )

    expected_links = {
        href
        for claim in draft.contacts
        if (href := contact_href(candidate, claim.fact_ids[0], claim.text)) is not None
    }
    actual_links = {value.rstrip("/") for value in evidence.geometry.links}
    if not {value.rstrip("/") for value in expected_links}.issubset(actual_links):
        groups["links"] = False
        issues.append(
            ValidationIssue(
                group="links",
                code="link-targets",
                message=f"found {sorted(actual_links)}",
            )
        )

    if (
        evidence.geometry.scroll_width > evidence.geometry.client_width + 1
        or evidence.geometry.offenders
    ):
        groups["visual"] = False
        issues.append(
            ValidationIssue(
                group="visual",
                code="overflow",
                message=str(evidence.geometry.offenders),
            )
        )
    expected_dir = "rtl" if draft.language == "he" else "ltr"
    if evidence.geometry.direction != expected_dir:
        groups["direction"] = False
        issues.append(
            ValidationIssue(
                group="direction",
                code="document-direction",
                message=str(evidence.geometry.direction),
            )
        )
    if draft.language == "he" and '<bdi dir="ltr">' not in evidence.html_text:
        groups["direction"] = False
        issues.append(
            ValidationIssue(
                group="direction",
                code="mixed-direction-isolation",
                message="No LTR isolation was rendered.",
            )
        )

    expected_filename = normalized_role_filename(profile.normalized_role, candidate)
    if evidence.pdf_name != expected_filename:
        groups["filename"] = False
        issues.append(
            ValidationIssue(
                group="filename",
                code="filename",
                message=f"expected {expected_filename}",
            )
        )

    return ValidationReport.from_findings(
        groups=groups,
        issues=issues,
        evidence={
            "page_count": evidence.page_count,
            "ats_claim_coverage": coverage,
            "pdf_sha256": evidence.pdf_sha256,
            "geometry": evidence.geometry.raw,
        },
    )


def _claim_recoverable(text: str, normalized_pdf: str, rtl: bool) -> bool:
    if not rtl:
        return normalized_text(text) in normalized_pdf
    # PDF extractors commonly reorder adjacent RTL narrative and isolated LTR tokens
    # (dates, percentages, B2B, product names). Requiring phrase order would reject a
    # readable tagged PDF. Require nearly every meaningful source token instead.
    tokens = [
        token.casefold()
        for token in re.findall(r"[\u0590-\u05ff]+|[A-Za-z]+|\d+", text)
        if len(token) > 1 or token.isdigit()
    ]
    if not tokens:
        return False
    recovered = sum(token in normalized_pdf for token in tokens)
    return recovered / len(tokens) >= 0.9


def _without_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", value)
