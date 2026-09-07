"""Composed views spanning both mechanisms: queries and the composition root."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol, Self

from ...domain.contracts.drafts import WorkingDraft
from ...domain.contracts.records import ApprovedRevision
from ..settings import SettingsRepository
from .composed_knowledge import KnowledgeAuditRepository
from .composed_tracking import TrackingRepository
from .repositories import (
    ApplicationStore,
    ArtifactRegistry,
    JobStore,
    OperationRepository,
    UnitOfWork,
    WorkingDraftReader,
)


class QueryRepository(
    ApplicationStore, JobStore, ArtifactRegistry, WorkingDraftReader, OperationRepository, Protocol
):
    """Read sources used to build storage-neutral query projections."""

    def read_transaction(self) -> AbstractContextManager[Self]: ...

    def working_draft(self, working_draft_id: str) -> WorkingDraft: ...

    def approved_revisions(self, application_id: str) -> list[ApprovedRevision]: ...

    def approved_revision(self, revision_id: str) -> ApprovedRevision: ...

    def decision_for_revision(self, revision_id: str) -> dict[str, Any]: ...

    def recruitment_events(self, application_id: str) -> list[dict[str, Any]]: ...

    def submissions(self, application_id: str) -> list[dict[str, Any]]: ...

    def audit_records(self, application_id: str) -> list[dict[str, Any]]: ...

    def integrity_check(self) -> list[str]: ...


class ApplicationRepository(
    TrackingRepository,
    KnowledgeAuditRepository,
    OperationRepository,
    SettingsRepository,
    Protocol,
):
    """Composition-root view of the adapter; services use focused ports above."""

    def unit_of_work(self) -> UnitOfWork: ...

    def integrity_check(self) -> list[str]: ...
