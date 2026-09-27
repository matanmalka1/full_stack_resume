"""Two approved resumes compared by claim and fact identity, not by line position."""

from __future__ import annotations

from cv_engine.domain.contracts.drafts import ClaimLine, DraftDocument
from cv_engine.domain.revision_comparison import compare_drafts


def _copy(draft: DraftDocument) -> DraftDocument:
    return draft.model_copy(deep=True)


def _section(draft: DraftDocument, name: str):
    return next(section for section in draft.sections if section.name == name)


def _changes(comparison, kind: str):
    return [
        (section.name, change)
        for section in comparison.sections
        for change in section.changes
        if change.kind == kind
    ]


def test_an_identical_revision_reports_every_line_unchanged(draft_factory) -> None:
    draft = draft_factory("Account Manager retention negotiation").draft

    comparison = compare_drafts(draft, _copy(draft))

    assert comparison.summary.added == comparison.summary.removed == 0
    assert comparison.summary.reworded == comparison.summary.moved == 0
    total = 1 + len(draft.contacts) + sum(len(section.claims) for section in draft.sections)
    assert comparison.summary.unchanged == total
    assert {section.status for section in comparison.sections} == {"unchanged"}
    assert not (comparison.profile_changed or comparison.language_changed)


def test_lines_are_followed_by_identity_through_rewording_moves_and_recreation(
    draft_factory,
) -> None:
    older = draft_factory("Account Manager retention negotiation").draft
    newer = _copy(older)
    sections = [section for section in newer.sections if len(section.claims) >= 3]
    first, second = sections[0], sections[1]

    # 1. Same claim, new wording.
    reworded = first.claims[0]
    old_text = reworded.text
    reworded.text = f"{old_text} (reworded)"
    # 2. Same claim, other section.
    moved = first.claims.pop(1)
    second.claims.append(moved)
    # 3. Same facts and style under a new claim id and new wording: still one statement.
    recreated = second.claims[0]
    second.claims[0] = recreated.model_copy(
        update={"claim_id": "recreated-claim", "text": f"{recreated.text} again"}
    )
    # 4. Same text under a new claim id: not a change at all.
    retyped = second.claims[1]
    second.claims[1] = retyped.model_copy(update={"claim_id": "retyped-claim"})
    # 5. Gone, and 6. new.
    removed = first.claims.pop()
    first.claims.append(
        ClaimLine(
            claim_id="brand-new",
            style="bullet",
            text="A line the older revision never had.",
            fact_ids=["fact-that-is-new"],
            claim_type="pending",
            text_hash="0" * 64,
            pending_reason="test",
        )
    )

    comparison = compare_drafts(older, newer)

    assert [
        (name, change.before_text, change.after_text)
        for name, change in _changes(comparison, "reworded")
    ] == [
        (first.name, old_text, reworded.text),
        (second.name, recreated.text, f"{recreated.text} again"),
    ]
    assert [(name, change.from_section) for name, change in _changes(comparison, "moved")] == [
        (second.name, first.name)
    ]
    assert [(name, change.before_text) for name, change in _changes(comparison, "removed")] == [
        (first.name, removed.text)
    ]
    assert [(name, change.after_text) for name, change in _changes(comparison, "added")] == [
        (first.name, "A line the older revision never had.")
    ]
    assert _section_status(comparison, first.name) == "changed"


def _section_status(comparison, name: str) -> str:
    return next(section.status for section in comparison.sections if section.name == name)


def test_sections_only_in_one_revision_are_added_or_removed_whole(draft_factory) -> None:
    older = draft_factory("Account Manager retention negotiation").draft
    newer = _copy(older)
    dropped = newer.sections.pop()

    comparison = compare_drafts(older, newer)

    assert comparison.sections[-1].name == dropped.name
    assert comparison.sections[-1].status == "removed"
    assert len(comparison.sections[-1].changes) == len(dropped.claims)
    reverse = compare_drafts(newer, older)
    assert _section_status(reverse, dropped.name) == "added"


def test_a_profile_change_is_reported_beside_the_line_changes(draft_factory) -> None:
    sales = draft_factory("Account Manager retention negotiation").draft
    development = draft_factory(
        "Python backend developer API React", profile_override="development"
    ).draft

    comparison = compare_drafts(sales, development)

    assert comparison.profile_changed
    assert comparison.sections[0].kind == "headline"
