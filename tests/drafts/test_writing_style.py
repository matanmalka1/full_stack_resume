"""Writing-style findings: deterministic advice that never blocks approval (§11)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cv_engine.domain.validation import validate_draft
from cv_engine.domain.writing_style import writing_findings

WRITING_CODES = {
    "weak-opener",
    "first-person",
    "long-bullet",
    "repeated-opener",
    "em-dash",
    "mixed-date-formats",
}


def _draft(language: str, *sections: list[tuple[str, str]]) -> SimpleNamespace:
    """A duck-typed draft: sections of (style, text) lines."""
    return SimpleNamespace(
        language=language,
        sections=[
            SimpleNamespace(
                claims=[
                    SimpleNamespace(claim_id=f"c{index}-{line}", style=style, text=text)
                    for line, (style, text) in enumerate(lines)
                ]
            )
            for index, lines in enumerate(sections)
        ],
    )


def _codes(draft: SimpleNamespace) -> list[str]:
    return [finding.code for finding in writing_findings(draft)]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("style", "text", "code"),
    [
        ("bullet", "Responsible for the EMEA renewal pipeline", "weak-opener"),
        ("bullet", "Helped with onboarding new hires", "weak-opener"),
        ("bullet", "Worked on the billing service", "weak-opener"),
        ("bullet", "I closed 12 enterprise deals", "first-person"),
        ("paragraph", "Account manager who grows my clients' revenue", "first-person"),
        ("bullet", "Closed 12 deals — all of them enterprise", "em-dash"),
        ("bullet", "Closed 12 deals -- all of them enterprise", "em-dash"),
        ("bullet", " ".join(["word"] * 36), "long-bullet"),
    ],
)
def test_a_line_rule_fires(style: str, text: str, code: str) -> None:
    assert _codes(_draft("en", [(style, text)])) == [code]


@pytest.mark.parametrize(
    ("style", "text"),
    [
        ("bullet", "Owned the EMEA renewal pipeline"),
        ("bullet", "Built I/O drivers for the ME region"),
        ("bullet", "Closed 12 deals – all of them enterprise"),
        ("bullet", "Built a well-known, state-of-the-art tool"),
        ("bullet", " ".join(["word"] * 35)),
        # Weak openers and length are about bullets; a heading or date is structure.
        ("paragraph", "Responsible for the EMEA renewal pipeline"),
        ("heading", "Account Manager — Payme"),
        ("date", "2019 -- 2021"),
    ],
)
def test_clean_or_structural_lines_raise_nothing(style: str, text: str) -> None:
    assert _codes(_draft("en", [(style, text)])) == []


def test_english_phrasing_rules_do_not_run_on_hebrew() -> None:
    # "I" and "Responsible for" in a Hebrew document are product names or quotes, not
    # the document's own voice; length and em dashes still apply.
    draft = _draft(
        "he",
        [
            ("bullet", "Responsible for ניהול לקוחות"),
            ("bullet", "I ניהול לקוחות — עשרות לקוחות"),
            ("bullet", " ".join(["מילה"] * 36)),
        ],
    )
    assert _codes(draft) == ["em-dash", "long-bullet"]


def test_three_bullets_of_one_entry_opening_alike_are_flagged_once() -> None:
    draft = _draft(
        "en",
        [
            ("heading", "Account Manager"),
            ("bullet", "Managed 40 accounts"),
            ("bullet", "managed renewals"),
            ("bullet", "Managed onboarding"),
            ("heading", "Sales Representative"),
            ("bullet", "Managed a territory"),
            ("bullet", "Managed renewals"),
        ],
    )
    assert _codes(draft) == ["repeated-opener"]


def test_two_alike_openers_per_entry_are_not_flagged_across_entries() -> None:
    draft = _draft(
        "en",
        [("heading", "A"), ("bullet", "Led X"), ("bullet", "Led Y")],
        [("heading", "B"), ("bullet", "Led Z")],
    )
    assert _codes(draft) == []


@pytest.mark.parametrize(
    ("language", "dates", "mixed"),
    [
        ("en", ["Jan 2020 - Mar 2022", "March 2018 - Dec 2019"], False),
        ("en", ["01/2020 - 03/2022", "03/2018 - 12/2019"], False),
        ("en", ["Jan 2020 - Present", "03/2018 - 12/2019"], True),
        ("en", ["2020-01 - 2022-03", "Jan 2018 - Dec 2019"], True),
        # Year-only ranges are a precision, not a format.
        ("en", ["Jan 2020 - Mar 2022", "2014 - 2018"], False),
        # Hebrew month names display as MM/YYYY, so the user's own numeric line agrees
        # with them, including a line the renderer cannot convert whole.
        ("he", ["אוגוסט 2020 - ינואר 2025", "03/2019 - 08/2020"], False),
        ("he", ["אוגוסט 2020 - היום", "מרץ 2019 - אוגוסט 2020"], False),
        ("he", ["Jan 2020 - היום", "מרץ 2019 - אוגוסט 2020"], True),
    ],
)
def test_mixed_date_formats_across_the_document(
    language: str, dates: list[str], mixed: bool
) -> None:
    draft = _draft(language, [("date", dates[0])], [("date", dates[1])])
    assert _codes(draft) == (["mixed-date-formats"] if mixed else [])


def test_writing_findings_are_warnings_that_do_not_block(draft_factory) -> None:
    facts, profile, analysis, draft, markdown = draft_factory(
        "Account Manager retention portfolio customer relationships", write=True
    )
    report = validate_draft(draft, markdown.read_text(encoding="utf-8"), facts, profile, analysis)

    assert report.passed, report.model_dump()
    writing = [issue for issue in report.issues if issue.code in WRITING_CODES]
    # The seeded Account Manager facts open three bullets of one role with "Managed".
    assert writing, report.model_dump()
    assert all(not issue.hard and issue.group == "content" for issue in writing)
    assert report.groups["content"]
