"""The database audit side of the file-backed Knowledge lifecycle."""

from __future__ import annotations

from typing import Any, Protocol

from ...domain.contracts.selection import AcceptedGap, SelectionManifest, SelectionPlan
from .repositories import FactAudit, KnowledgeMutationRepository, WorkingDraftReader


class KnowledgeAuditRepository(
    FactAudit, WorkingDraftReader, KnowledgeMutationRepository, Protocol
):
    """The database audit side of the file-backed Knowledge lifecycle.

    Promoting a manual claim reads the working draft the claim was edited in,
    so the port says so instead of relying on the adapter carrying more than
    the service declared.
    """

    def get_analysis(self, analysis_id: str) -> dict[str, Any]: ...

    def create_selection_plan(
        self,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        *,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        new_acceptances: list[AcceptedGap] | None = ...,
        expected_selection_plan_id: str | None = ...,
        enforce_expected_selection_plan: bool = ...,
        plan_id: str | None = ...,
        created_at: str | None = ...,
    ) -> SelectionPlan: ...

    def selection_plan(self, selection_plan_id: str) -> SelectionPlan: ...
