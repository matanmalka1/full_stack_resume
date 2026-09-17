from __future__ import annotations

from sqlalchemy import select

from ...application.errors import UnknownRecord
from ...application.ports.ready import ReadyEvidence
from ...application.ports.transactions import ReadTransaction
from .analysis_sql import _analysis_record, _selection_plan_record
from .artifacts_sql import (
    _artifact_version,
    _artifact_version_for_revision,
    _decision_for_artifact_version,
    _validation_for_artifact,
    _validation_lineage,
    _validation_report,
)
from .connection import SqlAlchemyTransactionManager
from .drafts_sql import _approved_revision, _latest_approved_revision
from .maintenance import _integrity_problems
from .tables import job_analyses, selection_plans


def _optional(call):
    try:
        return call()
    except UnknownRecord:
        return None


class SqlAlchemyReadyEvidenceReader:
    def __init__(self, transactions: SqlAlchemyTransactionManager):
        self._transactions = transactions

    def load(
        self,
        tx: ReadTransaction,
        application_id: str,
        revision_id: str | None = None,
        pdf_artifact_version_id: str | None = None,
    ) -> ReadyEvidence:
        connection = self._transactions.connection_for(tx)
        revision = (
            _approved_revision(connection, revision_id)
            if revision_id is not None
            else _latest_approved_revision(connection, application_id)
        )
        sources = {
            kind: value
            for kind in ("claim_manifest", "resume_markdown")
            if (
                value := _optional(
                    lambda kind=kind: _artifact_version_for_revision(
                        connection, revision.id, kind, "approved"
                    )
                )
            )
            is not None
        }
        rendered = {
            kind: value
            for kind in ("resume_html", "resume_pdf")
            if (
                value := _optional(
                    lambda kind=kind: _artifact_version_for_revision(
                        connection, revision.id, kind, "rendered"
                    )
                )
            )
            is not None
        }
        selected_pdf = (
            _optional(lambda: _artifact_version(connection, pdf_artifact_version_id))
            if pdf_artifact_version_id is not None
            else rendered.get("resume_pdf")
        )
        analysis_row = (
            connection.execute(
                select(job_analyses).where(job_analyses.c.id == revision.job_analysis_id)
            )
            .mappings()
            .one_or_none()
        )
        plan_row = (
            connection.execute(
                select(selection_plans).where(selection_plans.c.id == revision.selection_plan_id)
            )
            .mappings()
            .one_or_none()
        )
        markdown = sources.get("resume_markdown")
        approval_validation = _optional(
            lambda: _validation_report(connection, revision.validation_run_id)
        )
        approval_lineage = _optional(
            lambda: _validation_lineage(connection, revision.validation_run_id)
        )
        post_render = (
            _optional(
                lambda: _validation_for_artifact(
                    connection, application_id, "post-render", selected_pdf["id"]
                )
            )
            if selected_pdf is not None
            else None
        )
        return ReadyEvidence(
            revision=revision,
            source_artifacts=sources,
            rendered_artifacts=rendered,
            selected_pdf=selected_pdf,
            analysis=_analysis_record(analysis_row) if analysis_row is not None else None,
            plan=_selection_plan_record(plan_row) if plan_row is not None else None,
            decision=(
                _optional(lambda: _decision_for_artifact_version(connection, markdown["id"]))
                if markdown is not None
                else None
            ),
            approval_validation=approval_validation,
            approval_lineage=approval_lineage,
            post_render_validation=post_render,
            integrity_problems=tuple(_integrity_problems(connection)),
        )
