from __future__ import annotations

import pytest

from cv_engine.domain.date_display import (
    HEBREW_MONTHS,
    displayed_claim_text,
    displayed_date,
    numeric_date,
)

MONTHS = [
    ("ינואר", "01"),
    ("פברואר", "02"),
    ("מרץ", "03"),
    ("מרס", "03"),
    ("אפריל", "04"),
    ("מאי", "05"),
    ("יוני", "06"),
    ("יולי", "07"),
    ("אוגוסט", "08"),
    ("ספטמבר", "09"),
    ("אוקטובר", "10"),
    ("נובמבר", "11"),
    ("דצמבר", "12"),
]


def test_every_hebrew_month_is_known() -> None:
    assert {name for name, _ in MONTHS} == set(HEBREW_MONTHS)


@pytest.mark.parametrize(("month", "number"), MONTHS)
def test_every_month_converts_in_a_range_and_alone(month: str, number: str) -> None:
    assert numeric_date(f"{month} 2020 - ינואר 2025", "he") == f"{number}/2020 – 01/2025"
    assert numeric_date(f"ינואר 2019 - {month} 2020", "he") == f"01/2019 – {number}/2020"
    assert numeric_date(f"{month} 2021", "he") == f"{number}/2021"


@pytest.mark.parametrize(
    "text",
    [
        "אוגוסט 2020 - ינואר 2025",
        "אוגוסט 2020 – ינואר 2025",
        "אוגוסט 2020 — ינואר 2025",
        "אוגוסט 2020-ינואר 2025",
        "  אוגוסט 2020  –  ינואר 2025 ",
    ],
)
def test_any_dash_between_the_ends_becomes_a_spaced_en_dash(text: str) -> None:
    assert numeric_date(text, "he") == "08/2020 – 01/2025"


@pytest.mark.parametrize("text", ["2019-2020", "2019 - 2020", "2019 – 2020", "2019—2020"])
def test_a_year_range_is_normalized(text: str) -> None:
    assert numeric_date(text, "he") == "2019 – 2020"


@pytest.mark.parametrize(
    "text",
    [
        "אוגוסט 2020 - היום",
        "אוגוסט 2020 - הווה",
        "ינואר 2023 - כיום",
        "2020 - היום",
        "קיץ 2020",
        "אוגוסט 20 - ינואר 2025",
        "באוגוסט 2020 - ינואר 2025",
        "אוגוסט 2020 עד ינואר 2025",
        "2020",
        "",
    ],
)
def test_text_that_is_not_wholly_a_date_is_left_unchanged(text: str) -> None:
    assert numeric_date(text, "he") is None
    assert displayed_date(text, "he") == text


@pytest.mark.parametrize(
    "text", ["August 2020 - January 2025", "2019 - 2020", "אוגוסט 2020 - ינואר 2025"]
)
def test_other_languages_are_unchanged(text: str) -> None:
    assert numeric_date(text, "en") is None
    assert displayed_date(text, "en") == text


def test_only_date_lines_are_displayed_differently() -> None:
    assert displayed_claim_text("date", "מרץ 2019 - אוגוסט 2020", "he") == "03/2019 – 08/2020"
    assert displayed_claim_text("item", "מרץ 2019 - אוגוסט 2020", "he") == (
        "מרץ 2019 - אוגוסט 2020"
    )
