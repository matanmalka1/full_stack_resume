"""`PlaywrightRenderer.measure_pages` through a real Chromium.

Service fixtures swap the measurement for `PageCountingRenderer`, so the real
one is exercised only here. Browser-marked through `render_validator`, which
also renders the reference PDF the measurement is compared against.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdf import PdfReader
from test_golden import _build_case, _golden_cases

from cv_engine.domain.drafts import add_claim
from cv_engine.infrastructure.rendering import PlaywrightRenderer, render_html

PADDING_CLAIMS = 40


def _files_under(*roots: Path) -> set[Path]:
    return {path for root in roots if root.exists() for path in root.rglob("*")}


def _padded(draft, count: int):
    section = max(
        draft.sections,
        key=lambda candidate: sum(claim.style == "bullet" for claim in candidate.claims),
    )
    for index in range(count):
        draft, _ = add_claim(
            draft,
            section.name,
            f"Padding line {index}: delivered a measurable outcome for a cross-functional "
            "team, documented the result, and handed it over to the next owner.",
        )
    return draft


def test_measure_pages_counts_the_real_pdf_and_leaves_nothing_behind(
    services,
    render_validator,
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture, case = _golden_cases()[0]
    setup = _build_case(services, case)
    renderer = PlaywrightRenderer(services.paths.knowledge_root)

    # The measurement's temporary directory lands here, so "nothing left behind"
    # is checked against a directory no other process writes to.
    measure_tmp = tmp_path / "measure-tmp"
    measure_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(measure_tmp))
    watched = (services.paths.artifacts_root, services.paths.temp_root, measure_tmp)
    before = _files_under(*watched)

    measured = renderer.measure_pages(setup.draft, setup.candidate)
    padded = renderer.measure_pages(_padded(setup.draft, PADDING_CLAIMS), setup.candidate)

    assert _files_under(*watched) == before
    assert not any(measure_tmp.iterdir())

    assert measured == 1, fixture.stem
    assert padded > measured, (fixture.stem, padded)

    reference = tmp_path / "reference"
    reference.mkdir()
    html = render_html(
        setup.draft, services.paths.knowledge_root, reference / "resume.html", setup.candidate
    )
    pdf = reference / "resume.pdf"
    render_validator(setup.draft, setup.profile, html, pdf, setup.candidate)
    assert len(PdfReader(str(pdf)).pages) == measured, fixture.stem
