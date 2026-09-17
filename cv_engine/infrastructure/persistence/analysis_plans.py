"""Stateless transaction-token adapter for analysis and selection-plan writes."""

from __future__ import annotations

from sqlalchemy import select, update

from ...application.errors import UnknownRecord
from ...application.ports.transactions import ReadTransaction, WriteTransaction
from ...domain.contracts.analysis import JobAnalysis
from ...domain.contracts.selection import SelectionManifest, SelectionPlan
from ...util import utc_now
from .analysis_sql import (
    _create_selection_plan,
    _lock_application,
    _save_analysis,
    _selection_plan_record,
)
from .connection import SqlAlchemyTransactionManager
from .tables import applications, selection_plans


class SqlAlchemyAnalysisPlanRepository:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def lock_application(self, tx: WriteTransaction, application_id: str) -> None:
        _lock_application(self._transactions.connection_for(tx, access="write"), application_id)

    def save_analysis(
        self,
        tx: WriteTransaction,
        application_id: str,
        snapshot_id: str,
        analysis: JobAnalysis,
        plan: SelectionManifest,
        *,
        provider: str,
        model: str,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        expected_analysis_id: str | None = None,
        expected_selection_plan_id: str | None = None,
        enforce_expected_selection_plan: bool = False,
        refuse_matching_context_operation: bool = False,
    ) -> tuple[str, SelectionPlan]:
        return _save_analysis(
            self._transactions.connection_for(tx, access="write"),
            application_id,
            snapshot_id,
            analysis,
            plan,
            provider=provider,
            model=model,
            candidate_context_version=candidate_context_version,
            candidate_context_hash=candidate_context_hash,
            profile_version=profile_version,
            selection_policy_version=selection_policy_version,
            track_emphasis_dependencies=track_emphasis_dependencies,
            expected_analysis_id=expected_analysis_id,
            expected_selection_plan_id=expected_selection_plan_id,
            enforce_expected_selection_plan=enforce_expected_selection_plan,
            refuse_matching_context_operation=refuse_matching_context_operation,
        )

    def create_selection_plan(
        self,
        tx: WriteTransaction,
        application_id: str,
        job_analysis_id: str,
        plan: SelectionManifest,
        *,
        candidate_context_version: str,
        candidate_context_hash: str,
        profile_version: str,
        selection_policy_version: str,
        track_emphasis_dependencies: dict[str, str],
        expected_selection_plan_id: str | None = None,
        enforce_expected_selection_plan: bool = False,
        refuse_matching_context_operation: bool = False,
        plan_id: str | None = None,
        created_at: str | None = None,
    ) -> SelectionPlan:
        return _create_selection_plan(
            self._transactions.connection_for(tx, access="write"),
            application_id,
            job_analysis_id,
            plan,
            candidate_context_version=candidate_context_version,
            candidate_context_hash=candidate_context_hash,
            profile_version=profile_version,
            selection_policy_version=selection_policy_version,
            track_emphasis_dependencies=track_emphasis_dependencies,
            expected_selection_plan_id=expected_selection_plan_id,
            enforce_expected_selection_plan=enforce_expected_selection_plan,
            refuse_matching_context_operation=refuse_matching_context_operation,
            plan_id=plan_id,
            created_at=created_at,
        )

    def selection_plan(self, tx: ReadTransaction, selection_plan_id: str) -> SelectionPlan:
        row = (
            self._transactions.connection_for(tx)
            .execute(select(selection_plans).where(selection_plans.c.id == selection_plan_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise UnknownRecord(f"no selection plan {selection_plan_id}")
        return _selection_plan_record(row)

    def set_normalized_role(
        self, tx: WriteTransaction, application_id: str, normalized_role: str
    ) -> None:
        result = self._transactions.connection_for(tx, access="write").execute(
            update(applications)
            .where(applications.c.id == application_id)
            .values(normalized_role=normalized_role, updated_at=utc_now())
        )
        if result.rowcount != 1:
            raise UnknownRecord(application_id)
