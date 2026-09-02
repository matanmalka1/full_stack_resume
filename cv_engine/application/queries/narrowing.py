"""Product-owned narrowing, ordering, paging, and facets for Application lists."""

from __future__ import annotations

from typing import Any

from ...domain.models import ApplicationStatus
from .views import (
    ActivityFilter,
    ApplicationListItemView,
    ApplicationListQuery,
    ApplicationListView,
    ApplicationPreset,
    ApplicationSort,
    PreparationState,
)

_INTERVIEW_STATUSES = frozenset(
    {
        ApplicationStatus.RECRUITER_SCREEN,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.ASSIGNMENT,
        ApplicationStatus.FINAL_STAGE,
        ApplicationStatus.OFFER,
    }
)

CLOSED_RECRUITMENT_STATUSES = frozenset(
    {
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CLOSED,
    }
)


def application_is_closed(
    terminal_outcome: str | None, recruitment_status: str | ApplicationStatus
) -> bool:
    """Project whether recruitment is closed from the authoritative application rule."""
    return terminal_outcome is not None or recruitment_status in CLOSED_RECRUITMENT_STATUSES


def _matches_preset(item: ApplicationListItemView, preset: ApplicationPreset | None) -> bool:
    if preset is None:
        return True
    if preset is ApplicationPreset.NEEDS_ATTENTION:
        return bool(item.review_reasons or item.stale_reasons or item.warnings)
    if preset is ApplicationPreset.READY_TO_SEND:
        return item.latest_ready_revision_id is not None
    if preset is ApplicationPreset.ACTIVE_INTERVIEWS:
        return item.recruitment_status in _INTERVIEW_STATUSES
    raise ValueError(f"unsupported Application preset: {preset}")


def _matches_search(item: ApplicationListItemView, search: str) -> bool:
    """Search identity plus the two lifecycle codes exposed by the projection."""
    needle = search.strip().casefold()
    if not needle:
        return True
    return (
        needle
        in "\n".join(
            (item.company, item.target_role, item.preparation_state.value, item.recruitment_status)
        ).casefold()
    )


def _matches_activity(item: ApplicationListItemView, activity: ActivityFilter) -> bool:
    if activity is ActivityFilter.ALL:
        return True
    return item.is_closed is (activity is ActivityFilter.CLOSED)


def _matches_common(item: ApplicationListItemView, query: ApplicationListQuery) -> bool:
    return (
        _matches_activity(item, query.activity)
        and (not query.stages or item.preparation_state in query.stages)
        and _matches_search(item, query.search)
    )


_STAGE_ORDER = {state: index for index, state in enumerate(PreparationState)}


def _sort_key(sort: ApplicationSort) -> Any:
    if sort is ApplicationSort.COMPANY:
        return lambda item: (item.company.casefold(), item.target_role.casefold())
    if sort is ApplicationSort.CREATED:
        return lambda item: _descending(item.created_at)
    if sort is ApplicationSort.STAGE:
        return lambda item: (-_STAGE_ORDER[item.preparation_state], _descending(item.updated_at))
    return lambda item: _descending(item.updated_at)


class _Descending:
    """Reverse one sort field without reversing the whole compound key."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __lt__(self, other: _Descending) -> bool:
        return self.value > other.value


def _descending(value: str) -> _Descending:
    return _Descending(value)


def narrow_application_list(
    items: list[ApplicationListItemView], query: ApplicationListQuery
) -> ApplicationListView:
    """Apply one query and derive Dashboard facets from the same projected rows.

    A facet respects every other axis but ignores its own selection. This matches
    the former independent count queries while requiring only this one projection.
    """
    common = [item for item in items if _matches_common(item, query)]
    preset_base = [
        item
        for item in common
        if not query.recruitment_statuses or item.recruitment_status in query.recruitment_statuses
    ]
    recruitment_base = [item for item in common if _matches_preset(item, query.preset)]
    matched = sorted(
        (item for item in preset_base if _matches_preset(item, query.preset)),
        key=_sort_key(query.sort),
    )
    window = (
        matched[query.offset :]
        if query.limit is None
        else matched[query.offset : query.offset + query.limit]
    )

    stage_counts: dict[PreparationState, int] = {}
    for item in items:
        stage_counts[item.preparation_state] = stage_counts.get(item.preparation_state, 0) + 1

    preset_counts = {"all": len(preset_base)}
    for preset in ApplicationPreset:
        preset_counts[preset.value] = sum(_matches_preset(item, preset) for item in preset_base)

    recruitment_status_counts: dict[ApplicationStatus, int] = {}
    for item in recruitment_base:
        status = ApplicationStatus(item.recruitment_status)
        recruitment_status_counts[status] = recruitment_status_counts.get(status, 0) + 1

    return ApplicationListView(
        items=window,
        matched=len(matched),
        total=len(items),
        limit=query.limit,
        offset=query.offset,
        stage_counts=stage_counts,
        preset_counts=preset_counts,
        recruitment_status_counts=recruitment_status_counts,
    )
