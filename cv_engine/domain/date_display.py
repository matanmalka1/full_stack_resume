"""How a date line is displayed, as distinct from what its fact says.

A Hebrew month name next to digits splits into several bidi runs, and PDF text
extractors put those runs back in different orders: "אוגוסט 2020 - ינואר 2025"
comes out as "2025 - ינואר2020אוגוסט". An ATS cannot read that as a date range.
A Hebrew document therefore displays its date lines numerically, "08/2020 – 01/2025",
which the renderer isolates as one left-to-right run.

This is presentation only, like keyword emphasis: the fact, its rendering, the
stored claim, and the Markdown export keep the wording the user wrote. A line is
converted completely or not at all; anything this cannot read whole ("היום",
free text) is displayed exactly as written.
"""

from __future__ import annotations

import re

HEBREW_MONTHS: dict[str, int] = {
    "ינואר": 1,
    "פברואר": 2,
    "מרץ": 3,
    "מרס": 3,
    "אפריל": 4,
    "מאי": 5,
    "יוני": 6,
    "יולי": 7,
    "אוגוסט": 8,
    "ספטמבר": 9,
    "אוקטובר": 10,
    "נובמבר": 11,
    "דצמבר": 12,
}

#: Between the two ends of a displayed range: an en dash with a space either side.
RANGE_SEPARATOR = " – "

_MONTH = "|".join(sorted(HEBREW_MONTHS, key=len, reverse=True))
_DASH = r"\s*[-–—]\s*"
_MONTH_YEAR = rf"({_MONTH})\s+(\d{{4}})"
_MONTH_RANGE = re.compile(rf"{_MONTH_YEAR}{_DASH}{_MONTH_YEAR}")
_LONE_MONTH = re.compile(_MONTH_YEAR)
_YEAR_RANGE = re.compile(rf"(\d{{4}}){_DASH}(\d{{4}})")


def _month_year(month: str, year: str) -> str:
    return f"{HEBREW_MONTHS[month]:02d}/{year}"


def numeric_date(text: str, language: str) -> str | None:
    """The numeric form of a whole date line, or None when it is not one this can read.

    Only Hebrew is converted. Accepts "<month> YYYY - <month> YYYY", a lone
    "<month> YYYY", and "YYYY - YYYY", with a hyphen, en dash or em dash between.
    """
    if language != "he":
        return None
    value = text.strip()
    if match := _MONTH_RANGE.fullmatch(value):
        start = _month_year(match[1], match[2])
        end = _month_year(match[3], match[4])
        return f"{start}{RANGE_SEPARATOR}{end}"
    if match := _LONE_MONTH.fullmatch(value):
        return _month_year(match[1], match[2])
    if match := _YEAR_RANGE.fullmatch(value):
        return f"{match[1]}{RANGE_SEPARATOR}{match[2]}"
    return None


def displayed_date(text: str, language: str) -> str:
    """What a date line shows: its numeric form, or the text unchanged."""
    return numeric_date(text, language) or text


def displayed_claim_text(style: str, text: str, language: str) -> str:
    """The text a rendered claim shows. Only date lines differ from the claim."""
    return displayed_date(text, language) if style == "date" else text
