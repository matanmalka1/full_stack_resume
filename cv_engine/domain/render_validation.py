from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .candidate import contact_href
from .models import CandidateContext, DraftDocument, Profile, ValidationIssue, ValidationReport
from ..util import normalized_text


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
    screenshot_path: str
    screenshot_exists: bool
    screenshot_size: int
    geometry: RenderGeometry


def normalized_role_filename(role: str, candidate: CandidateContext) -> str:
    cleaned = re.sub(r"\b(?:senior|junior|lead|principal)\b", "", role, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^A-Za-z0-9+ /&.-]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    if not cleaned:
        cleaned = "B2B Sales"
    return f"{candidate.resolved_filename_name} - {cleaned} - CV.pdf"


def validate_render_evidence(
    draft: DraftDocument,
    profile: Profile,
    evidence: RenderEvidence,
    candidate: CandidateContext,
) -> ValidationReport:
    groups = dict.fromkeys(RENDER_VALIDATION_GROUPS, True)
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

    maximum = 2 if profile.allow_two_pages else 1
    if evidence.page_count < 1 or evidence.page_count > maximum:
        groups["page_count"] = False
        issues.append(
            ValidationIssue(
                group="page_count",
                code="page-count",
                message=f"{evidence.page_count} pages; maximum {maximum}",
            )
        )

    claim_texts = [draft.headline.text, *(claim.text for claim in draft.contacts)]
    claim_texts.extend(claim.text for section in draft.sections for claim in section.claims)
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
    if not evidence.screenshot_exists or evidence.screenshot_size == 0:
        groups["visual"] = False
        issues.append(
            ValidationIssue(
                group="visual",
                code="screenshot-missing",
                message=evidence.screenshot_path,
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
            "screenshot": evidence.screenshot_path,
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
