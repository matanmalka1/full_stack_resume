from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup
from pypdf import PdfReader

from ..domain.candidate import contact_href
from ..domain.models import (
    CandidateContext,
    DraftDocument,
    Profile,
    ValidationIssue,
    ValidationReport,
)
from ..util import normalized_text, sha256_file


MIXED_LTR = re.compile(
    r"(?:https?://\S+|[\w.+-]+@[\w.-]+|\+?\d[\d() .-]{5,}|\b(?:B2B|CRM|ERP|KPIs?|SaaS|Full-Stack|"
    r"Priority ERP|Excel|WhatsApp|Teams|Python|FastAPI|React|PostgreSQL|API|APIs|PDF|CI/CD|OpenAPI|"
    r"GitHub Actions|Node\.js|TypeScript|JavaScript|Flask|Express|SQL|AWS EC2|LLM)\b|\d+(?:[.-]\d+)*%?)"
)


def normalized_role_filename(role: str, candidate: CandidateContext) -> str:
    cleaned = re.sub(r"\b(?:senior|junior|lead|principal)\b", "", role, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^A-Za-z0-9+ /&.-]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    if not cleaned:
        cleaned = "B2B Sales"
    return f"{candidate.resolved_filename_name} - {cleaned} - CV.pdf"


def _bidi(value: str, rtl: bool) -> Markup:
    escaped = html.escape(value)
    if not rtl:
        return Markup(escaped)
    parts: list[str] = []
    cursor = 0
    for match in MIXED_LTR.finditer(value):
        parts.append(html.escape(value[cursor:match.start()]))
        parts.append(f'<bdi dir="ltr">{html.escape(match.group(0))}</bdi>')
        cursor = match.end()
    parts.append(html.escape(value[cursor:]))
    return Markup("".join(parts))


def _contact_html(claim: Any, rtl: bool, candidate: CandidateContext) -> Markup:
    text = claim.text
    href = contact_href(candidate, claim.fact_ids[0], text)
    if href is None:
        return _bidi(text, rtl)
    return Markup(f'<a href="{html.escape(href)}">{_bidi(text, rtl)}</a>')


def render_html(
    draft: DraftDocument, repo: Path, output_path: Path, candidate: CandidateContext
) -> Path:
    rtl = draft.language == "he"
    if draft.track.value == "development":
        template_name = "development_ltr.html.j2"
    elif rtl:
        template_name = "sales_rtl.html.j2"
    else:
        template_name = "sales_ltr.html.j2"
    environment = Environment(
        loader=FileSystemLoader(repo / "rendering" / "templates"),
        autoescape=select_autoescape(("html", "j2")),
        undefined=StrictUndefined,
    )
    template = environment.get_template(template_name)
    sections = [
        {
            "name": section.name,
            "claims": [
                {"style": claim.style, "html": _bidi(claim.text, rtl)}
                for claim in section.claims
            ],
        }
        for section in draft.sections
    ]
    rendered = template.render(
        name=draft.name,
        headline=_bidi(draft.headline.text, rtl),
        headline_text=draft.headline.text,
        contacts=[_contact_html(claim, rtl, candidate) for claim in draft.contacts],
        sections=sections,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite rendered HTML: {output_path}")
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


class BrowserUnavailableError(RuntimeError):
    """The rendering browser could not be started in this environment."""


SANDBOX_SIGNATURES = (
    "bootstrap_check_in",
    "Permission denied (1100)",
    "kr == KERN_SUCCESS",
    "TransformProcessType",
    "RegisterApplication",
)


def _launch_failure_message(detail: str) -> str:
    lines = [f"Rendering browser failed to start: {detail.strip()}"]
    if any(signature in detail for signature in SANDBOX_SIGNATURES):
        lines.append(
            "The OS sandbox blocked the browser's Mach port registration. Chrome's "
            "--no-sandbox flag does not bypass this; it only disables Chrome's own sandbox."
        )
    else:
        lines.append(
            "Likely causes: browsers are not installed "
            "(./.venv/bin/python -m playwright install chromium), or an OS sandbox is "
            "blocking browser startup."
        )
    lines.append(
        "Run rendering outside the sandboxed session, or select the non-browser test "
        'subset with: pytest -m "not browser".'
    )
    return "\n".join(lines)


def _chrome_path() -> str | None:
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]
    return str(next((path for path in candidates if path.is_file()), "")) or None


def render_pdf(html_path: Path, pdf_path: Path, screenshot_path: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for PDF rendering") from exc
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists() or screenshot_path.exists():
        raise FileExistsError("refusing to overwrite rendered PDF or screenshot")
    with sync_playwright() as playwright:
        launch_options: dict[str, Any] = {"headless": True}
        chrome = _chrome_path()
        if chrome:
            launch_options["executable_path"] = chrome
        try:
            browser = playwright.chromium.launch(**launch_options)
        except Exception as exc:
            raise BrowserUnavailableError(_launch_failure_message(str(exc))) from exc
        page = browser.new_page(viewport={"width": 1123, "height": 1588}, device_scale_factor=1)
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        geometry = page.evaluate("""() => {
          const page = document.querySelector('[data-cv-page]');
          const rect = page.getBoundingClientRect();
          const offenders = [...document.querySelectorAll('.claim, h1, h2, .contacts')]
            .filter(el => { const r = el.getBoundingClientRect(); return r.left < rect.left - 1 || r.right > rect.right + 1 || r.bottom > rect.bottom + 1; })
            .map(el => el.textContent.trim().slice(0, 100));
          return {scrollWidth: page.scrollWidth, clientWidth: page.clientWidth,
                  scrollHeight: page.scrollHeight, clientHeight: page.clientHeight,
                  offenders, dir: document.documentElement.dir,
                  links: [...document.querySelectorAll('a')].map(a => a.href)};
        }""")
        page.screenshot(path=str(screenshot_path), full_page=True)
        page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True)
        browser.close()
    return geometry


def validate_rendered(
    draft: DraftDocument,
    profile: Profile,
    html_path: Path,
    pdf_path: Path,
    screenshot_path: Path,
    geometry: dict[str, Any],
    candidate: CandidateContext,
) -> ValidationReport:
    groups = {
        "render": True,
        "page_count": True,
        "pdf": True,
        "ats": True,
        "links": True,
        "visual": True,
        "direction": True,
        "filename": True,
    }
    issues: list[ValidationIssue] = []
    if not html_path.is_file() or html_path.stat().st_size == 0:
        groups["render"] = False
        issues.append(ValidationIssue(group="render", code="html-missing", message=str(html_path)))
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        groups["pdf"] = False
        issues.append(ValidationIssue(group="pdf", code="pdf-missing", message=str(pdf_path)))
        return ValidationReport(passed=False, groups=groups, issues=issues)
    try:
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        groups["pdf"] = False
        issues.append(ValidationIssue(group="pdf", code="pdf-corrupt", message=str(exc)))
        page_count, extracted = 0, ""
    maximum = 2 if profile.allow_two_pages else 1
    if page_count < 1 or page_count > maximum:
        groups["page_count"] = False
        issues.append(ValidationIssue(group="page_count", code="page-count", message=f"{page_count} pages; maximum {maximum}"))

    claim_texts = [draft.headline.text, *(claim.text for claim in draft.contacts)]
    claim_texts.extend(claim.text for section in draft.sections for claim in section.claims)
    normalized_pdf = normalized_text(extracted)
    found = sum(_claim_recoverable(text, normalized_pdf, draft.language == "he") for text in claim_texts)
    coverage = found / len(claim_texts) if claim_texts else 0
    if coverage < 0.9:
        groups["ats"] = False
        issues.append(ValidationIssue(group="ats", code="text-coverage", message=f"PDF text coverage is {coverage:.1%}"))

    # Expected links are derived from the contacts this document actually
    # carries, so the check follows the candidate's canonical facts instead of
    # a list that has to be remembered separately.
    expected_links = {
        href for claim in draft.contacts
        if (href := contact_href(candidate, claim.fact_ids[0], claim.text)) is not None
    }
    actual_links = {value.rstrip("/") for value in geometry.get("links", [])}
    if not {value.rstrip("/") for value in expected_links}.issubset(actual_links):
        groups["links"] = False
        issues.append(ValidationIssue(group="links", code="link-targets", message=f"found {sorted(actual_links)}"))

    if geometry.get("scrollWidth", 0) > geometry.get("clientWidth", 0) + 1 or geometry.get("offenders"):
        groups["visual"] = False
        issues.append(ValidationIssue(group="visual", code="overflow", message=str(geometry.get("offenders", []))))
    if not screenshot_path.is_file() or screenshot_path.stat().st_size == 0:
        groups["visual"] = False
        issues.append(ValidationIssue(group="visual", code="screenshot-missing", message=str(screenshot_path)))
    expected_dir = "rtl" if draft.language == "he" else "ltr"
    html_text = html_path.read_text(encoding="utf-8")
    if geometry.get("dir") != expected_dir:
        groups["direction"] = False
        issues.append(ValidationIssue(group="direction", code="document-direction", message=str(geometry.get("dir"))))
    if draft.language == "he" and '<bdi dir="ltr">' not in html_text:
        groups["direction"] = False
        issues.append(ValidationIssue(group="direction", code="mixed-direction-isolation", message="No LTR isolation was rendered."))
    expected_filename = normalized_role_filename(profile.normalized_role, candidate)
    if pdf_path.name != expected_filename:
        groups["filename"] = False
        issues.append(ValidationIssue(group="filename", code="filename", message=f"expected {expected_filename}"))

    return ValidationReport(
        passed=all(groups.values()),
        groups=groups,
        issues=issues,
        evidence={
            "page_count": page_count,
            "ats_claim_coverage": coverage,
            "pdf_sha256": sha256_file(pdf_path),
            "screenshot": str(screenshot_path),
            "geometry": geometry,
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


class PlaywrightRenderer:
    """The real renderer: Jinja templates, managed Chromium, and pypdf checks.

    Wraps the module functions so the application layer depends on a port it
    can substitute, while the rendering rules themselves stay exactly where
    they were.
    """

    def __init__(self, knowledge_root: Path):
        self.knowledge_root = Path(knowledge_root)

    def render_html(
        self, draft: DraftDocument, output_path: Path, candidate: CandidateContext
    ) -> Path:
        return render_html(draft, self.knowledge_root, output_path, candidate)

    def render_pdf(
        self, html_path: Path, pdf_path: Path, screenshot_path: Path
    ) -> dict[str, Any]:
        return render_pdf(html_path, pdf_path, screenshot_path)

    def validate_rendered(
        self,
        draft: DraftDocument,
        profile: Profile,
        html_path: Path,
        pdf_path: Path,
        screenshot_path: Path,
        geometry: dict[str, Any],
        candidate: CandidateContext,
    ) -> ValidationReport:
        return validate_rendered(
            draft, profile, html_path, pdf_path, screenshot_path, geometry, candidate
        )

    def filename_for(self, normalized_role: str, candidate: CandidateContext) -> str:
        return normalized_role_filename(normalized_role, candidate)
