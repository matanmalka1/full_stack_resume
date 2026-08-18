from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup
from pypdf import PdfReader

from ..application.errors import InfrastructureFailure
from ..domain.candidate import contact_href
from ..domain.models import (
    CandidateContext,
    DraftDocument,
    Profile,
    ValidationReport,
)
from ..domain.render_validation import (
    RenderEvidence,
    RenderGeometry,
    normalized_role_filename,
    validate_render_evidence,
)
from ..domain.render_validation import (
    _claim_recoverable as _claim_recoverable,
)
from ..util import sha256_file

MIXED_LTR = re.compile(
    r"(?:https?://\S+|[\w.+-]+@[\w.-]+|\+?\d[\d() .-]{5,}|\b(?:B2B|CRM|ERP|KPIs?|SaaS|Full-Stack|"
    r"Priority ERP|Excel|WhatsApp|Teams|Python|FastAPI|React|PostgreSQL|API|APIs|PDF|CI/CD|OpenAPI|"
    r"GitHub Actions|Node\.js|TypeScript|JavaScript|Flask|Express|SQL|AWS EC2|LLM)\b|\d+(?:[.-]\d+)*%?)"
)


def _bidi(value: str, rtl: bool) -> Markup:
    escaped = html.escape(value)
    if not rtl:
        return Markup(escaped)
    parts: list[str] = []
    cursor = 0
    for match in MIXED_LTR.finditer(value):
        parts.append(html.escape(value[cursor : match.start()]))
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
                {"style": claim.style, "html": _bidi(claim.text, rtl)} for claim in section.claims
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


class BrowserUnavailableError(InfrastructureFailure):
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
    delivered_pdf_filename: str | None = None,
) -> ValidationReport:
    evidence = collect_render_evidence(
        draft,
        profile,
        html_path,
        pdf_path,
        screenshot_path,
        geometry,
        candidate,
        delivered_pdf_filename,
    )
    return validate_render_evidence(draft, profile, evidence, candidate)


def collect_render_evidence(
    _draft: DraftDocument,
    _profile: Profile,
    html_path: Path,
    pdf_path: Path,
    screenshot_path: Path,
    geometry: dict[str, Any],
    _candidate: CandidateContext,
    delivered_pdf_filename: str | None = None,
) -> RenderEvidence:
    html_exists = html_path.is_file()
    html_size = html_path.stat().st_size if html_exists else 0
    pdf_exists = pdf_path.is_file()
    pdf_size = pdf_path.stat().st_size if pdf_exists else 0
    screenshot_exists = screenshot_path.is_file()
    screenshot_size = screenshot_path.stat().st_size if screenshot_exists else 0
    page_count = 0
    extracted = ""
    pdf_error = None
    html_text = ""
    pdf_sha256 = None
    if pdf_exists and pdf_size:
        try:
            reader = PdfReader(str(pdf_path))
            page_count = len(reader.pages)
            extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            pdf_error = str(exc)
        html_text = html_path.read_text(encoding="utf-8")
        pdf_sha256 = sha256_file(pdf_path)

    return RenderEvidence(
        html_path=str(html_path),
        html_exists=html_exists,
        html_size=html_size,
        html_text=html_text,
        pdf_path=str(pdf_path),
        pdf_name=delivered_pdf_filename or pdf_path.name,
        pdf_exists=pdf_exists,
        pdf_size=pdf_size,
        pdf_error=pdf_error,
        page_count=page_count,
        extracted_text=extracted,
        pdf_sha256=pdf_sha256,
        screenshot_path=str(screenshot_path),
        screenshot_exists=screenshot_exists,
        screenshot_size=screenshot_size,
        geometry=RenderGeometry(
            scroll_width=geometry.get("scrollWidth", 0),
            client_width=geometry.get("clientWidth", 0),
            scroll_height=geometry.get("scrollHeight", 0),
            client_height=geometry.get("clientHeight", 0),
            offenders=geometry.get("offenders", []),
            direction=geometry.get("dir"),
            links=geometry.get("links", []),
            raw=geometry,
        ),
    )


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

    def render_pdf(self, html_path: Path, pdf_path: Path, screenshot_path: Path) -> dict[str, Any]:
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
        delivered_pdf_filename: str | None = None,
    ) -> ValidationReport:
        return validate_rendered(
            draft,
            profile,
            html_path,
            pdf_path,
            screenshot_path,
            geometry,
            candidate,
            delivered_pdf_filename,
        )

    def filename_for(self, normalized_role: str, candidate: CandidateContext) -> str:
        return normalized_role_filename(normalized_role, candidate)
