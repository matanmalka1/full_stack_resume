from __future__ import annotations

from typing import Any


def resolve_job_snapshot_id(repository: Any, application_id: str) -> str:
    """The snapshot a legacy caller meant when it named none.

    v2 commands take explicit source IDs. v1 signatures do not carry one, so
    the resolution happens here, in the compatibility layer, where `latest` is
    a query convenience rather than part of what a command means.
    """
    return repository.latest_snapshot(application_id)["id"]


def resolve_job_analysis_id(repository: Any, application_id: str) -> str:
    """The analysis a legacy caller meant when it named none."""
    return repository.latest_analysis(application_id)[0]


def resolve_selection_plan_id(repository: Any, application_id: str) -> str:
    """The immutable plan a legacy caller meant when it named none."""
    return repository.latest_selection_plan(application_id).id


__all__ = [
    "resolve_job_analysis_id",
    "resolve_job_snapshot_id",
    "resolve_selection_plan_id",
]
