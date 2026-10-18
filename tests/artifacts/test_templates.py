from __future__ import annotations

import re
from pathlib import Path

import pytest
from test_rendering import _displayed_lines, _evidence

from cv_engine.domain.date_display import displayed_claim_text
from cv_engine.domain.render_validation import validate_render_evidence
from cv_engine.domain.templates import TEMPLATES, is_side_section, section_columns, template_spec
from cv_engine.infrastructure.rendering import compose_html

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "catalog"


def test_every_template_has_a_page_and_no_page_names_an_unknown_template() -> None:
    pages = {path.name.removesuffix(".html.j2") for path in TEMPLATE_DIR.glob("*.html.j2")}
    assert pages - {"base"} == set(TEMPLATES)
    assert template_spec(None) is None
    with pytest.raises(ValueError, match="unknown template"):
        template_spec("nope")


def test_no_template_styles_text_in_a_way_an_ats_reads_apart() -> None:
    # Spaced letters split a heading in pdfminer; small caps and opacity drop or
    # replace glyphs in the PDF text layer. A negative tracking on the name is fine.
    for path in TEMPLATE_DIR.glob("*.html.j2"):
        css = path.read_text(encoding="utf-8")
        assert not re.search(r"letter-spacing:\s*[.\d]*[1-9]", css), path.name
        assert not re.search(r"font-variant[^;]*small-caps|(?<![\w-])opacity\s*:", css), path.name


def test_a_two_column_template_puts_list_sections_in_its_side_column(draft_factory) -> None:
    draft = draft_factory("Account Manager retention portfolio").draft
    side = [section.name for section in draft.sections if is_side_section(section)]
    main = [section.name for section in draft.sections if not is_side_section(section)]
    assert side and main

    def names(template: str | None) -> list[list[str]]:
        return [[section.name for section in column] for column in section_columns(draft, template)]

    assert names(None) == [[section.name for section in draft.sections]]
    assert names("latex") == names(None)
    assert names("two-column") == [main, side]
    assert names("deedy") == [side, main]


@pytest.mark.parametrize("language", ["en", "he"])
@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_each_template_renders_every_line_in_its_column(
    project_root: Path, draft_factory, template: str, language: str
) -> None:
    setup = draft_factory("Account Manager retention portfolio", language_override=language)
    html = compose_html(setup.draft, project_root, setup.candidate, template)
    direction = "rtl" if language == "he" else "ltr"
    assert f'<html lang="{language}" dir="{direction}">' in html
    assert f'class="page t-{template}"' in html
    order = [html.index(f'data-section="{section.name}"') for section in setup.draft.sections]
    columns = section_columns(setup.draft, template)
    expected = [setup.draft.sections.index(section) for column in columns for section in column]
    assert sorted(range(len(order)), key=order.__getitem__) == expected
    assert html.count('class="bullet claim"') == sum(
        claim.style == "bullet" for section in setup.draft.sections for claim in section.claims
    )
    if TEMPLATES[template].columns == 2:
        assert 'class="column column-side"' in html


def test_two_columns_may_interleave_but_each_reads_in_order(draft_factory) -> None:
    setup = draft_factory("Account Manager retention portfolio")
    main, side = section_columns(setup.draft, "two-column")

    def lines(sections) -> list[str]:
        return [line for section in sections for line in [section.name, *_section_lines(section)]]

    # Read side by side, a section of each column at a time, as pdfminer may.
    interleaved: list[str] = []
    for index in range(max(len(main), len(side))):
        interleaved += lines(main[index : index + 1]) + lines(side[index : index + 1])
    header = _displayed_lines(setup.draft)[: 1 + len(setup.draft.contacts)]
    text = "\n".join([*header, *interleaved])
    report = validate_render_evidence(
        setup.draft, setup.profile, _evidence(setup, text), setup.candidate, "two-column"
    )
    assert report.passed, report.issues
    # The same text is out of order for one column.
    report = validate_render_evidence(
        setup.draft, setup.profile, _evidence(setup, text), setup.candidate
    )
    assert "reading-order" in {issue.code for issue in report.issues}

    # Within a column, the order still holds.
    swapped = "\n".join([*header, *lines([main[1], main[0], *main[2:]]), *lines(side)])
    report = validate_render_evidence(
        setup.draft, setup.profile, _evidence(setup, swapped), setup.candidate, "two-column"
    )
    assert [issue.code for issue in report.issues] == ["reading-order"]


def _section_lines(section) -> list[str]:
    return [displayed_claim_text(claim.style, claim.text, "en") for claim in section.claims]
