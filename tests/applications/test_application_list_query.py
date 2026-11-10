"""The Application list query: what it narrows, how it orders, and how it pages.

`narrow_application_list` is a pure function over already-projected rows, so these
exercise it directly rather than through a database. What it operates on -
`preparation_state` - is computed by the §9 projection and is covered against real
records in `test_state_projection.py`; what is under test here is the query applied
to that projection, which is the part a client would otherwise be re-deriving.
"""

from __future__ import annotations

import pytest

from cv_engine.application.queries import (
    ApplicationListItemView,
    ApplicationListQuery,
    ApplicationPreset,
    ApplicationSort,
    ContentCheck,
    PreparationState,
    ReasonView,
    WarningView,
    narrow_application_list,
)


def item(
    application_id: str = "app-1",
    *,
    company: str = "Acme",
    target_role: str = "Backend Engineer",
    preparation_state: PreparationState = PreparationState.NEEDS_ANALYSIS,
    created_at: str = "2026-08-24T07:00:00Z",
    updated_at: str = "2026-08-24T07:00:00Z",
) -> ApplicationListItemView:
    return ApplicationListItemView(
        id=application_id,
        company=company,
        target_role=target_role,
        preparation_state=preparation_state,
        content_check=ContentCheck.NONE,
        job_text_hash="1" * 64,
        created_at=created_at,
        updated_at=updated_at,
    )


def ids(items: list[ApplicationListItemView]) -> list[str]:
    return [entry.id for entry in items]


def test_no_query_is_the_whole_list_most_recently_updated_first() -> None:
    """The default has to stay the old behavior: every caller that reads the list
    without a query - the CSV export among them - gets everything."""
    rows = [
        item("old", updated_at="2026-08-01T00:00:00Z"),
        item("new", updated_at="2026-08-29T00:00:00Z"),
        item("middle", updated_at="2026-08-15T00:00:00Z"),
    ]

    result = narrow_application_list(rows, ApplicationListQuery())

    assert ids(result.items) == ["new", "middle", "old"]
    assert result.total == 3
    assert result.matched == 3


def test_stages_narrow_to_the_named_states_and_an_empty_set_narrows_nothing() -> None:
    rows = [
        item("a", preparation_state=PreparationState.NEEDS_ANALYSIS),
        item("b", preparation_state=PreparationState.READY),
        item("c", preparation_state=PreparationState.DRAFT_IN_PROGRESS),
    ]

    named = narrow_application_list(
        rows,
        ApplicationListQuery(
            stages=frozenset({PreparationState.READY, PreparationState.DRAFT_IN_PROGRESS})
        ),
    )
    assert sorted(ids(named.items)) == ["b", "c"]

    assert narrow_application_list(rows, ApplicationListQuery()).matched == 3


def test_query_matrix() -> None:
    """Search, every sort, the stage tie-break and paging, one row per behaviour.

    - Search covers identity and the preparation state code; whitespace is not a filter.
    - Each sort orders by its own field. Created and updated disagree on purpose,
      so a sort reading the wrong field is visible rather than passing by
      coincidence; stage sorts furthest along first.
    - The stage key sorts one field ascending-by-negation and the other
      descending, which `reverse=True` cannot express: it would flip the tie-break.
    - A page is a window on the ordering and the counts place it; paging windows
      what the filter matched, not the whole list.
    - An offset past the end is what a client holding a stale page number asks
      for: an empty page rather than a refusal, with counts that say the page is gone.
    """
    searchable = [
        item("a", company="Acme"),
        item("b", company="Binat", target_role="Account Manager"),
        item("c", company="Cegal", preparation_state=PreparationState.READY),
    ]
    sortable = [
        item(
            "zeta",
            company="Zeta",
            updated_at="2026-08-01T00:00:00Z",
            created_at="2026-08-20T00:00:00Z",
        ),
        item(
            "alpha",
            company="Alpha",
            preparation_state=PreparationState.READY,
            updated_at="2026-08-29T00:00:00Z",
            created_at="2026-08-02T00:00:00Z",
        ),
    ]
    tied = [
        item("early", preparation_state=PreparationState.READY, updated_at="2026-08-01T00:00:00Z"),
        item("late", preparation_state=PreparationState.READY, updated_at="2026-08-29T00:00:00Z"),
        item("behind", preparation_state=PreparationState.NEEDS_ANALYSIS),
    ]
    paged = [
        item(f"app-{index}", updated_at=f"2026-08-{index + 10:02d}T00:00:00Z") for index in range(5)
    ]
    filtered = [
        item("ready-1", preparation_state=PreparationState.READY),
        item("ready-2", preparation_state=PreparationState.READY),
        item("behind-1"),
    ]

    # (label, rows, query, expected ids, ordered?, expected (matched, total))
    cases = [
        ("search company", searchable, ApplicationListQuery(search="binat"), ["b"], True, (1, 3)),
        ("search role", searchable, ApplicationListQuery(search="account"), ["b"], True, (1, 3)),
        ("search state", searchable, ApplicationListQuery(search="ready"), ["c"], True, (1, 3)),
        (
            "blank search",
            searchable,
            ApplicationListQuery(search="   "),
            ["a", "b", "c"],
            False,
            (3, 3),
        ),
        (
            "sort updated",
            sortable,
            ApplicationListQuery(sort=ApplicationSort.UPDATED),
            ["alpha", "zeta"],
            True,
            (2, 2),
        ),
        (
            "sort created",
            sortable,
            ApplicationListQuery(sort=ApplicationSort.CREATED),
            ["zeta", "alpha"],
            True,
            (2, 2),
        ),
        (
            "sort company",
            sortable,
            ApplicationListQuery(sort=ApplicationSort.COMPANY),
            ["alpha", "zeta"],
            True,
            (2, 2),
        ),
        (
            "sort stage",
            sortable,
            ApplicationListQuery(sort=ApplicationSort.STAGE),
            ["alpha", "zeta"],
            True,
            (2, 2),
        ),
        (
            "stage tie-break",
            tied,
            ApplicationListQuery(sort=ApplicationSort.STAGE),
            ["late", "early", "behind"],
            True,
            (3, 3),
        ),
        (
            "page window",
            paged,
            ApplicationListQuery(limit=2, offset=1),
            ["app-3", "app-2"],
            True,
            (5, 5),
        ),
        (
            "page after filter",
            filtered,
            ApplicationListQuery(stages=frozenset({PreparationState.READY}), limit=1),
            None,
            True,
            (2, 3),
        ),
        (
            "offset past end",
            [item("a")],
            ApplicationListQuery(limit=10, offset=50),
            [],
            True,
            (1, 1),
        ),
    ]
    for label, rows, query, expected, ordered, counts in cases:
        result = narrow_application_list(rows, query)
        found = ids(result.items)
        if expected is None:
            assert len(found) == 1, label
        elif ordered:
            assert found == expected, label
        else:
            assert sorted(found) == expected, label
        assert (result.matched, result.total) == counts, label
        assert (result.limit, result.offset) == (query.limit, query.offset), label


def test_stage_counts_are_over_every_application_not_the_narrowed_page() -> None:
    """A client offering a stage filter cannot learn the stages from the page that
    filter produced: the stage it selected is the only one that page holds. So the
    counts are taken before narrowing, and a state nothing has reached is absent
    rather than present as zero."""
    rows = [
        item("a", preparation_state=PreparationState.NEEDS_ANALYSIS),
        item("b", preparation_state=PreparationState.NEEDS_ANALYSIS),
        item("c", preparation_state=PreparationState.READY),
    ]

    narrowed = narrow_application_list(
        rows, ApplicationListQuery(stages=frozenset({PreparationState.READY}))
    )

    assert ids(narrowed.items) == ["c"]
    assert narrowed.stage_counts == {
        PreparationState.NEEDS_ANALYSIS: 2,
        PreparationState.READY: 1,
    }


def test_preset_counts_respect_the_other_filters_but_not_the_preset() -> None:
    rows = [
        item("ready-acme", company="Acme", preparation_state=PreparationState.READY),
        item("ready-binat", company="Binat", preparation_state=PreparationState.READY),
        item("behind-acme", company="Acme"),
    ]

    result = narrow_application_list(
        rows, ApplicationListQuery(search="acme", preset=ApplicationPreset.READY_TO_SEND)
    )

    assert ids(result.items) == ["ready-acme"]
    assert result.preset_counts == {"all": 2, "needs_attention": 0, "ready_to_send": 1}


def test_needs_attention_is_a_review_reason_and_a_warning_alone_is_not() -> None:
    """A warning disables nothing (§8): the preset lists what waits on a decision."""
    blocked = item("blocked").model_copy(
        update={
            "review_reasons": [ReasonView(code="PENDING_FACT_REQUIRES_RESOLUTION", message="m")]
        }
    )
    warned = item("warned").model_copy(
        update={"warnings": [WarningView(code="DOCUMENT_ON_OLDER_ANALYSIS", message="m")]}
    )

    result = narrow_application_list(
        [blocked, warned, item("quiet")],
        ApplicationListQuery(preset=ApplicationPreset.NEEDS_ATTENTION),
    )

    assert ids(result.items) == ["blocked"]
    assert result.preset_counts["needs_attention"] == 1


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (201, 0), (None, -1)])
def test_the_query_refuses_a_page_it_cannot_answer(limit: int | None, offset: int) -> None:
    """The bounds belong to the query rather than to one way of asking it, so a
    caller that is not the HTTP boundary is held to them too."""
    with pytest.raises(ValueError):
        ApplicationListQuery(limit=limit, offset=offset)
