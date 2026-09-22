from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cv_engine.domain.candidate import contact_href
from cv_engine.domain.render_validation import RenderEvidence, RenderGeometry
from cv_engine.infrastructure.rendering import render_pdf, validate_rendered


@pytest.fixture
def deterministic_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    def render_without_browser(html_path: Path, pdf_path: Path) -> dict[str, Any]:
        pdf_path.write_bytes(b"%PDF-1.4\n% deterministic integrity-test artifact\n")
        html = html_path.read_text(encoding="utf-8")
        direction = "rtl" if '<html lang="he" dir="rtl">' in html else "ltr"
        return {
            "scrollWidth": 100,
            "clientWidth": 100,
            "scrollHeight": 100,
            "clientHeight": 100,
            "offenders": [],
            "dir": direction,
            "links": [],
        }

    def deterministic_render_evidence(
        draft,
        _profile,
        html_path,
        pdf_path,
        geometry,
        candidate,
        delivered_pdf_filename=None,
    ) -> RenderEvidence:
        extracted_text = "\n".join(
            [
                draft.headline.text,
                *(claim.text for claim in draft.contacts),
                *(claim.text for section in draft.sections for claim in section.claims),
            ]
        )
        links = [
            href
            for claim in draft.contacts
            if (href := contact_href(candidate, claim.fact_ids[0], claim.text)) is not None
        ]
        complete_geometry = {**geometry, "links": links}
        return RenderEvidence(
            html_path=str(html_path),
            html_exists=True,
            html_size=html_path.stat().st_size,
            html_text=html_path.read_text(encoding="utf-8"),
            pdf_path=str(pdf_path),
            pdf_name=delivered_pdf_filename or pdf_path.name,
            pdf_exists=True,
            pdf_size=pdf_path.stat().st_size,
            pdf_error=None,
            page_count=1,
            extracted_text=extracted_text,
            pdf_sha256="deterministic-integrity-double",
            geometry=RenderGeometry(
                scroll_width=complete_geometry["scrollWidth"],
                client_width=complete_geometry["clientWidth"],
                scroll_height=complete_geometry["scrollHeight"],
                client_height=complete_geometry["clientHeight"],
                offenders=complete_geometry["offenders"],
                direction=complete_geometry["dir"],
                links=complete_geometry["links"],
                raw=complete_geometry,
            ),
        )

    monkeypatch.setattr("cv_engine.infrastructure.rendering.render_pdf", render_without_browser)
    monkeypatch.setattr(
        "cv_engine.infrastructure.rendering.collect_render_evidence",
        deterministic_render_evidence,
    )


@pytest.fixture
def render_validator():
    def validate(draft, profile, html: Path, pdf: Path, candidate):
        geometry = render_pdf(html, pdf)
        report = validate_rendered(draft, profile, html, pdf, geometry, candidate)
        return geometry, report

    return validate
