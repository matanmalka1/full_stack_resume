from __future__ import annotations

from typing import Literal, Protocol

from ....domain.contracts.records import AuditRecord
from ....domain.contracts.recruitment import ApplicationStatus
from ....domain.contracts.validation import ReadyQualification
from ....domain.recruitment import terminal_outcome_after
from ....util import new_id
from ...commands import ExternalSubmissionCommand, SubmissionCommand, SubmissionResult, WriteClient
from ...errors import StateConflict, UnknownRecord, ValidationBlocked
from ...ports.application_intake import AuditLogWriter
from ...ports.artifact_catalog import ArtifactCatalog
from ...ports.recruitment import RecruitmentStore
from ...ports.submission import SubmissionContextReader
from ...ports.transactions import TransactionManager


class ReadyQualifier(Protocol):
    def ready_qualification(
        self,
        application_id: str,
        approved_revision_id: str | None = None,
        pdf_artifact_version_id: str | None = None,
    ) -> ReadyQualification: ...


class SubmissionService:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        contexts: SubmissionContextReader,
        recruitment: RecruitmentStore,
        artifacts: ArtifactCatalog,
        audit: AuditLogWriter,
        ready: ReadyQualifier,
    ):
        self._transactions, self._contexts, self._recruitment = transactions, contexts, recruitment
        self._artifacts, self._audit, self._ready = artifacts, audit, ready

    def _context(self, application_id: str, revision_id: str | None):
        with self._transactions.read() as tx:
            context = self._contexts.load(tx, application_id, revision_id)
        if context.application.get("deleted_at") is not None:
            raise StateConflict(f"application is deleted: {application_id}")
        return context

    def submit_application(self, command: SubmissionCommand) -> SubmissionResult:
        context = self._context(command.application_id, command.approved_revision_id)
        revision = context.revision
        if revision is None or revision.application_id != command.application_id:
            raise StateConflict("approved revision belongs to another application")
        qualification = self._ready.ready_qualification(
            command.application_id, revision.id, command.pdf_artifact_version_id
        )
        if (
            not qualification.ready_qualified
            or qualification.pdf_artifact_version_id != command.pdf_artifact_version_id
        ):
            raise ValidationBlocked(
                "submission blocked by tampered Ready evidence (stale or mismatched)",
                qualification.validation,
            )
        warnings = []
        if context.latest_snapshot_id != revision.job_snapshot_id:
            warnings.append("READY_REVISION_FOR_OLDER_SNAPSHOT")
        if context.latest_analysis_id != revision.job_analysis_id:
            warnings.append("READY_REVISION_FOR_OLDER_ANALYSIS")
        if context.latest_selection_plan_id != revision.selection_plan_id:
            warnings.append("READY_REVISION_FOR_OLDER_SELECTION_PLAN")
        return self._record(
            context.application,
            "internal",
            revision.id,
            command.pdf_artifact_version_id,
            command.submitted_at,
            command.metadata,
            command.actor_type,
            command.client,
            warnings,
        )

    def record_external_submission(self, command: ExternalSubmissionCommand) -> SubmissionResult:
        context = self._context(command.application_id, None)
        if command.artifact_version_id is not None:
            with self._transactions.read() as tx:
                try:
                    artifact = self._artifacts.artifact_version(tx, command.artifact_version_id)
                except UnknownRecord as exc:
                    raise UnknownRecord(
                        f"unknown external submission source: {exc.args[0]}"
                    ) from exc
            if artifact["application_id"] != command.application_id:
                raise StateConflict("external submission artifact belongs to another application")
        return self._record(
            context.application,
            "external",
            None,
            command.artifact_version_id,
            command.submitted_at,
            command.metadata,
            command.actor_type,
            command.client,
            [],
        )

    def _record(
        self,
        application: dict,
        submission_type: str,
        revision_id: str | None,
        artifact_id: str | None,
        submitted_at: str,
        metadata: dict,
        actor_type: Literal["user", "system"],
        client: WriteClient,
        warnings: list[str],
    ) -> SubmissionResult:
        application_id, submission_id = application["id"], new_id()
        current, event_id = ApplicationStatus(application["current_status"]), None
        with self._transactions.write() as tx:
            self._recruitment.insert_submission(
                tx,
                submission_id,
                application_id,
                submission_type,
                revision_id,
                artifact_id,
                submitted_at,
                metadata,
            )
            if current is ApplicationStatus.SAVED:
                event_id = self._recruitment.insert_event(
                    tx,
                    application_id=application_id,
                    expected_current_status=current.value,
                    target_status="applied",
                    event_type="status_transition",
                    reason="submission recorded",
                    actor_type=actor_type,
                    client=client,
                    occurred_at=submitted_at,
                    terminal_outcome=terminal_outcome_after(
                        application.get("terminal_outcome"), ApplicationStatus.APPLIED
                    ),
                )
            self._audit.insert_audit(
                tx,
                AuditRecord(
                    id=new_id(),
                    application_id=application_id,
                    action="submit_application"
                    if submission_type == "internal"
                    else "record_external_submission",
                    entity_type="submission",
                    entity_id=submission_id,
                    actor_type=actor_type,
                    client=client,
                    occurred_at=submitted_at,
                    details={
                        "submission_type": submission_type,
                        "approved_revision_id": revision_id,
                        "artifact_version_id": artifact_id,
                    },
                ),
            )
        with self._transactions.read() as tx:
            updated = self._recruitment.application(tx, application_id)
        return SubmissionResult(
            application_id=application_id,
            submission_id=submission_id,
            approved_revision_id=revision_id,
            pdf_artifact_version_id=artifact_id,
            current_status=updated["current_status"],
            terminal_outcome=updated.get("terminal_outcome"),
            next_action=updated.get("next_action"),
            next_action_date=updated.get("next_action_date"),
            event_id=event_id,
            warnings=warnings,
        )
