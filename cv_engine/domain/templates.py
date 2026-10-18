"""The render templates a user can choose for a CV, and how each lays out sections.

A template is presentation only, like date display and keyword emphasis: it never
adds, removes, or rewords a claim. No template (`None`) means the track's own
template (`development_ltr`, `sales_ltr`, `sales_rtl`), which is what every
document used before templates could be chosen.

The chosen designs are ports of Resume Matcher's templates (Apache-2.0,
https://github.com/srbhr/Resume-Matcher). Every one renders in both directions.

A two-column template puts the list sections - those whose lines are all `item`
(education, skills, tools, languages) - in a side column and the rest in the main
column. The order the columns appear in the HTML is the order an ATS is expected
to read them; each column must read in its own order, while the two may interleave.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

from .contracts.drafts import DraftDocument, ResumeSection

TemplateName = Literal[
    "single-column",
    "two-column",
    "modern",
    "modern-two-column",
    "clean",
    "latex",
    "vivid",
    "vivid-single",
    "deedy",
    "modern-deedy",
]
TEMPLATE_NAMES: tuple[str, ...] = get_args(TemplateName)
#: The languages the template sample CV is written in.
SampleLanguage = Literal["en", "he"]
#: A template to preview: a chosen one, or `track` for the track's own.
PreviewTemplate = Literal[TemplateName, "track"]


def preview_template(name: str) -> str | None:
    """The template a preview names, `None` for the track's own."""
    return None if name == "track" else name


@dataclass(frozen=True, slots=True)
class TemplateSpec:
    id: TemplateName
    label: str
    description: str
    columns: int = 1
    #: For two columns: whether the side column comes first in the HTML (and on the
    #: reading side of the page: left in English, right in Hebrew).
    sidebar_first: bool = False
    #: The bullet glyph, which is real text in the PDF.
    marker: str = "•"


TEMPLATES: dict[str, TemplateSpec] = {
    spec.id: spec
    for spec in (
        TemplateSpec("single-column", "עמודה אחת", "כותרות מודגשות עם קו, טור יחיד."),
        TemplateSpec("two-column", "שתי עמודות", "טור ראשי וטור צד לכישורים ולשפות.", columns=2),
        TemplateSpec("modern", "מודרני", "צבע הדגשה בכותרות ומתחת לשם."),
        TemplateSpec(
            "modern-two-column",
            "מודרני בשתי עמודות",
            "צבע הדגשה, טור ראשי וטור צד.",
            columns=2,
        ),
        TemplateSpec("clean", "נקי", "מינימליסטי, כותרות אפורות דקות."),
        TemplateSpec("latex", "LaTeX", "גופן סריף אקדמי, כותרות עם קו מלא."),
        TemplateSpec(
            "vivid",
            "חי",
            "שם דו־גוני וכותרות צבעוניות, שתי עמודות.",
            columns=2,
            marker="›",
        ),
        TemplateSpec("vivid-single", "חי בעמודה אחת", "שם דו־גוני וכותרות צבעוניות.", marker="›"),
        TemplateSpec(
            "deedy",
            "Deedy",
            "שם דק וגדול, טור צד צר לפני הטור הראשי.",
            columns=2,
            sidebar_first=True,
        ),
        TemplateSpec("modern-deedy", "Deedy מודרני", "צפוף, טור יחיד, כותרות אפורות."),
    )
}


if tuple(TEMPLATES) != TEMPLATE_NAMES:
    raise RuntimeError("TemplateName and TEMPLATES must name the same templates in one order")


def template_spec(template: str | None) -> TemplateSpec | None:
    """The spec of a chosen template, `None` for the track default.

    Raises `ValueError` for a name that is not a template, so a stored value that
    no longer names one fails loudly instead of rendering something else.
    """
    if template is None:
        return None
    try:
        return TEMPLATES[template]
    except KeyError:
        raise ValueError(f"unknown template: {template}") from None


def is_side_section(section: ResumeSection) -> bool:
    """A list section, which a two-column template places in its side column."""
    return bool(section.claims) and all(claim.style == "item" for claim in section.claims)


def section_columns(draft: DraftDocument, template: str | None) -> list[list[ResumeSection]]:
    """The document's sections per column, in the order the HTML holds them."""
    spec = template_spec(template)
    if spec is None or spec.columns == 1:
        return [list(draft.sections)]
    side = [section for section in draft.sections if is_side_section(section)]
    main = [section for section in draft.sections if not is_side_section(section)]
    columns = [side, main] if spec.sidebar_first else [main, side]
    return [column for column in columns if column]
