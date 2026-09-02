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
    ActivityFilter,
    ApplicationListItemView,
    ApplicationListQuery,
    ApplicationSort,
    PreparationState,
    WorkingDraftState,
    narrow_application_list,
)


def item(
    application_id: str = "app-1",
    *,
    company: str = "Acme",
    target_role: str = "Backend Engineer",
    recruitment_status: str = "saved",
    terminal_outcome: str | None = None,
    preparation_state: PreparationState = PreparationState.NEEDS_ANALYSIS,
    created_at: str = "2026-08-24T07:00:00Z",
    updated_at: str = "2026-08-24T07:00:00Z",
) -> ApplicationListItemView:
    is_closed = terminal_outcome is not None or recruitment_status in {
        "rejected",
        "withdrawn",
        "closed",
    }
    return ApplicationListItemView(
        id=application_id,
        company=company,
        target_role=target_role,
        current_status=recruitment_status,
        recruitment_status=recruitment_status,
        terminal_outcome=terminal_outcome,
        is_closed=is_closed,
        preparation_state=preparation_state,
        working_draft_state=WorkingDraftState.NONE,
        active_job_snapshot_id="snap-1",
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
        item("closed", recruitment_status="rejected", updated_at="2026-08-15T00:00:00Z"),
    ]

    result = narrow_application_list(rows, ApplicationListQuery())

    # Most recently updated first, and a closed Application is not hidden by a
    # query that did not ask for the open ones.
    assert ids(result.items) == ["new", "closed", "old"]
    assert result.total == 3
    assert result.matched == 3


@pytest.mark.parametrize(
    ("activity", "expected"),
    [
        (ActivityFilter.OPEN, ["open"]),
        (ActivityFilter.CLOSED, ["by-status", "by-outcome"]),
        (ActivityFilter.ALL, ["open", "by-status", "by-outcome"]),
    ],
)
def test_activity_splits_the_recruitment_axis(
    activity: ActivityFilter, expected: list[str]
) -> None:
    """A closing status closes the Application on its own.

    `terminal_outcome` is the record's own answer and wins wherever it is set, but
    it is nullable: a row reading `rejected` must not count as open because the
    column beside it was never written.
    """
    rows = [
        item("open"),
        item("by-status", recruitment_status="rejected"),
        item("by-outcome", recruitment_status="interview", terminal_outcome="rejected"),
    ]

    result = narrow_application_list(
        rows, ApplicationListQuery(activity=activity, sort=ApplicationSort.CREATED)
    )

    assert sorted(ids(result.items)) == sorted(expected)
    assert result.matched == len(expected)
    # The count before narrowing, so a client can say how much it is not showing.
    assert result.total == 3


def test_stages_narrow_to_the_named_states_and_an_empty_set_narrows_nothing() -> None:
    rows = [
        item("a", preparation_state=PreparationState.NEEDS_ANALYSIS),
        item("b", preparation_state=PreparationState.READY),
        item("c", preparation_state=PreparationState.NEEDS_REVIEW),
    ]

    named = narrow_application_list(
        rows,
        ApplicationListQuery(
            stages=frozenset({PreparationState.READY, PreparationState.NEEDS_REVIEW})
        ),
    )
    assert sorted(ids(named.items)) == ["b", "c"]

    assert narrow_application_list(rows, ApplicationListQuery()).matched == 3


def test_search_covers_identity_and_both_lifecycle_codes() -> None:
    rows = [
        item("a", company="Acme"),
        item("b", company="Binat", target_role="Account Manager"),
        item("c", company="Cegal", preparation_state=PreparationState.READY),
    ]

    def matched(search: str) -> list[str]:
        return ids(narrow_application_list(rows, ApplicationListQuery(search=search)).items)

    assert matched("binat") == ["b"]
    assert matched("account") == ["b"]
    assert matched("ready") == ["c"]
    # Whitespace is not a filter.
    assert sorted(matched("   ")) == ["a", "b", "c"]


def test_each_sort_orders_by_its_own_field() -> None:
    rows = [
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

    def ordered(sort: ApplicationSort) -> list[str]:
        return ids(narrow_application_list(rows, ApplicationListQuery(sort=sort)).items)

    assert ordered(ApplicationSort.UPDATED) == ["alpha", "zeta"]
    # Created and updated disagree here on purpose, so a sort reading the wrong
    # field is visible rather than passing by coincidence.
    assert ordered(ApplicationSort.CREATED) == ["zeta", "alpha"]
    assert ordered(ApplicationSort.COMPANY) == ["alpha", "zeta"]
    # Furthest along first.
    assert ordered(ApplicationSort.STAGE) == ["alpha", "zeta"]


def test_stage_sort_breaks_ties_by_most_recently_updated() -> None:
    """The stage key sorts one field ascending-by-negation and the other descending,
    which `reverse=True` cannot express: it would flip the tie-break too."""
    rows = [
        item("early", preparation_state=PreparationState.READY, updated_at="2026-08-01T00:00:00Z"),
        item("late", preparation_state=PreparationState.READY, updated_at="2026-08-29T00:00:00Z"),
        item("behind", preparation_state=PreparationState.NEEDS_ANALYSIS),
    ]

    result = narrow_application_list(rows, ApplicationListQuery(sort=ApplicationSort.STAGE))

    assert ids(result.items) == ["late", "early", "behind"]


def test_a_page_is_a_window_on_the_ordering_and_the_counts_place_it() -> None:
    rows = [
        item(f"app-{index}", updated_at=f"2026-08-{index + 10:02d}T00:00:00Z") for index in range(5)
    ]

    page = narrow_application_list(rows, ApplicationListQuery(limit=2, offset=1))

    # Most recently updated first, so the second and third of that ordering.
    assert ids(page.items) == ["app-3", "app-2"]
    assert (page.matched, page.total) == (5, 5)
    assert (page.limit, page.offset) == (2, 1)


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


def test_dashboard_facets_ignore_their_own_axis_and_keep_other_filters() -> None:
    rows = [
        item("screen", recruitment_status="recruiter_screen"),
        item("interview", recruitment_status="interview"),
        item(
            "ready",
            recruitment_status="offer",
            preparation_state=PreparationState.READY,
        ),
        item("closed", recruitment_status="closed"),
    ]

    result = narrow_application_list(
        rows,
        ApplicationListQuery(
            activity=ActivityFilter.OPEN,
            recruitment_statuses=frozenset({"interview"}),
        ),
    )

    assert ids(result.items) == ["interview"]
    assert result.preset_counts == {
        "all": 1,
        "needs_attention": 0,
        "ready_to_send": 0,
        "active_interviews": 1,
    }
    assert result.recruitment_status_counts == {
        "recruiter_screen": 1,
        "interview": 1,
        "offer": 1,
    }


def test_paging_windows_what_the_filter_matched_not_the_whole_list() -> None:
    rows = [item("open-1"), item("open-2"), item("closed-1", recruitment_status="closed")]

    page = narrow_application_list(
        rows, ApplicationListQuery(activity=ActivityFilter.OPEN, limit=1)
    )

    assert len(page.items) == 1
    assert page.matched == 2
    assert page.total == 3


def test_an_offset_past_the_end_is_an_empty_page_rather_than_a_refusal() -> None:
    """What a client holding a stale page number asks for. The counts that come
    back are what tell it the page is gone."""
    result = narrow_application_list([item("a")], ApplicationListQuery(limit=10, offset=50))

    assert result.items == []
    assert result.matched == 1


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (201, 0), (None, -1)])
def test_the_query_refuses_a_page_it_cannot_answer(limit: int | None, offset: int) -> None:
    """The bounds belong to the query rather than to one way of asking it, so a
    caller that is not the HTTP boundary is held to them too."""
    with pytest.raises(ValueError):
        ApplicationListQuery(limit=limit, offset=offset)
