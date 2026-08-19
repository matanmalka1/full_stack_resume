from __future__ import annotations

from typing import Literal

from ...domain.models import ApplicationStatus, AuditRecord
from ...domain.recruitment import terminal_outcome_after, transition_allowed
from ...util import new_id, utc_now
from ..commands import (
    ApplicationMutationResult,
    ExternalSubmissionCommand,
    NextActionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    SubmissionCommand,
    SubmissionResult,
)
from ..errors import StateConflict, UnknownRecord, ValidationBlocked
from ..ports import TrackingRepository
from ..ready import qualify_ready_revision
from .base import ServiceBase


class TrackingService(ServiceBase[TrackingRepository]):
    """Append-only recruitment commands over a transactionally current projection."""

    def _result(self, application_id: str, *, event_id: str | None = None):
        application = self.repo.get_application(application_id)
        return ApplicationMutationResult(
            application_id=application_id,
            current_status=application["current_status"],
            terminal_outcome=application.get("terminal_outcome"),
            next_action=application.get("next_action"),
            next_action_date=application.get("next_action_date"),
            event_id=event_id,
        )

    def _audit(
        self,
        repository: TrackingRepository,
        *,
        application_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        actor_type: Literal["user", "system"],
        client: Literal["web", "cli", "worker"],
        occurred_at: str,
        details: dict | None = None,
    ) -> None:
        repository.insert_audit(
            AuditRecord(
                id=new_id(),
                application_id=application_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_type=actor_type,
                client=client,
                installation_id=self.installation_id,
                occurred_at=occurred_at,
                details=details or {},
            )
        )

    def transition_status(self, command: RecruitmentStatusCommand) -> ApplicationMutationResult:
        try:
            application = self.repo.get_application(command.application_id)
            current = ApplicationStatus(application["current_status"])
            target = ApplicationStatus(command.target_status)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        if target is ApplicationStatus.APPLIED:
            raise StateConflict("applied is submission-owned and cannot be set directly")
        if target is current:
            return self._result(command.application_id)
        if not transition_allowed(current, target):
            raise StateConflict(f"invalid status transition: {current.value} -> {target.value}")
        now = command.occurred_at or utc_now()
        event_id = new_id()
        try:
            with self.repo.unit_of_work() as uow:
                transaction = self.repo.bind(uow)
                transaction.insert_recruitment_event(
                    application_id=command.application_id,
                    expected_current_status=current.value,
                    target_status=target.value,
                    event_type="status_transition",
                    reason=command.reason,
                    actor_type=command.actor_type,
                    client=command.client,
                    installation_id=self.installation_id,
                    occurred_at=now,
                    terminal_outcome=terminal_outcome_after(
                        application.get("terminal_outcome"), target
                    ),
                    event_id=event_id,
                )
                self._audit(
                    transaction,
                    application_id=command.application_id,
                    action="transition_recruitment_status",
                    entity_type="recruitment_event",
                    entity_id=event_id,
                    actor_type=command.actor_type,
                    client=command.client,
                    occurred_at=now,
                    details={"from_status": current.value, "to_status": target.value},
                )
                uow.commit()
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        return self._result(command.application_id, event_id=event_id)

    def correct_recruitment_status(
        self, command: RecruitmentCorrectionCommand
    ) -> ApplicationMutationResult:
        if not command.reason.strip():
            raise StateConflict("recruitment correction reason is required")
        try:
            application = self.repo.get_application(command.application_id)
            current = ApplicationStatus(application["current_status"])
            target = ApplicationStatus(command.target_status)
            corrected = self.repo.recruitment_event(command.corrects_event_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown recruitment correction source: {exc.args[0]}") from exc
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        if corrected["application_id"] != command.application_id:
            raise StateConflict("a correction cannot reference another application's event")
        if corrected["event_type"] == "next_action":
            raise StateConflict("a status correction must reference a status event")
        now = command.occurred_at or utc_now()
        event_id = new_id()
        try:
            with self.repo.unit_of_work() as uow:
                transaction = self.repo.bind(uow)
                transaction.insert_recruitment_event(
                    application_id=command.application_id,
                    expected_current_status=current.value,
                    target_status=target.value,
                    event_type="status_correction",
                    reason=command.reason.strip(),
                    actor_type=command.actor_type,
                    client=command.client,
                    installation_id=self.installation_id,
                    occurred_at=now,
                    terminal_outcome=terminal_outcome_after(
                        application.get("terminal_outcome"), target
                    ),
                    corrects_event_id=command.corrects_event_id,
                    event_id=event_id,
                )
                self._audit(
                    transaction,
                    application_id=command.application_id,
                    action="correct_recruitment_status",
                    entity_type="recruitment_event",
                    entity_id=event_id,
                    actor_type=command.actor_type,
                    client=command.client,
                    occurred_at=now,
                    details={
                        "corrects_event_id": command.corrects_event_id,
                        "from_status": current.value,
                        "to_status": target.value,
                        "reason": command.reason.strip(),
                    },
                )
                uow.commit()
        except KeyError as exc:
            raise UnknownRecord(f"unknown recruitment correction source: {exc.args[0]}") from exc
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        return self._result(command.application_id, event_id=event_id)

    def set_next_action(self, command: NextActionCommand) -> ApplicationMutationResult:
        now = command.occurred_at or utc_now()
        try:
            with self.repo.unit_of_work() as uow:
                transaction = self.repo.bind(uow)
                event_id = transaction.insert_next_action_event(
                    application_id=command.application_id,
                    next_action=command.next_action,
                    next_action_date=command.next_action_date,
                    actor_type=command.actor_type,
                    client=command.client,
                    installation_id=self.installation_id,
                    occurred_at=now,
                )
                self._audit(
                    transaction,
                    application_id=command.application_id,
                    action="set_next_action",
                    entity_type="recruitment_event",
                    entity_id=event_id,
                    actor_type=command.actor_type,
                    client=command.client,
                    occurred_at=now,
                    details={
                        "next_action": command.next_action,
                        "next_action_date": command.next_action_date,
                    },
                )
                uow.commit()
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        return self._result(command.application_id, event_id=event_id)

    def submit_application(self, command: SubmissionCommand) -> SubmissionResult:
        try:
            application = self.repo.get_application(command.application_id)
            revision = self.repo.approved_revision(command.approved_revision_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown submission source: {exc.args[0]}") from exc
        if revision.application_id != command.application_id:
            raise StateConflict("approved revision belongs to another application")
        qualification = qualify_ready_revision(
            self.artifacts,
            self.repo,
            command.application_id,
            command.approved_revision_id,
            command.pdf_artifact_version_id,
        )
        if not qualification.ready_qualified:
            raise ValidationBlocked(
                "submission blocked by stale or tampered Ready evidence: "
                f"{[issue.code for issue in qualification.validation.issues]}"
            )
        if qualification.pdf_artifact_version_id != command.pdf_artifact_version_id:
            raise ValidationBlocked("submission PDF does not match the qualified revision")
        warnings: list[str] = []
        latest_snapshot = self.repo.latest_snapshot(command.application_id)
        if latest_snapshot["id"] != revision.job_snapshot_id:
            warnings.append("READY_REVISION_FOR_OLDER_SNAPSHOT")
        analyses = self.repo.analyses(command.application_id)
        if analyses and analyses[-1]["id"] != revision.job_analysis_id:
            warnings.append("READY_REVISION_FOR_OLDER_ANALYSIS")
        return self._record_submission(
            application=application,
            submission_type="internal",
            approved_revision_id=revision.id,
            artifact_version_id=command.pdf_artifact_version_id,
            submitted_at=command.submitted_at,
            metadata=command.metadata,
            actor_type=command.actor_type,
            client=command.client,
            warnings=warnings,
        )

    def record_external_submission(self, command: ExternalSubmissionCommand) -> SubmissionResult:
        try:
            application = self.repo.get_application(command.application_id)
            if command.artifact_version_id is not None:
                artifact = self.repo.artifact_version(command.artifact_version_id)
                if artifact["application_id"] != command.application_id:
                    raise StateConflict(
                        "external submission artifact belongs to another application"
                    )
        except KeyError as exc:
            raise UnknownRecord(f"unknown external submission source: {exc.args[0]}") from exc
        return self._record_submission(
            application=application,
            submission_type="external",
            approved_revision_id=None,
            artifact_version_id=command.artifact_version_id,
            submitted_at=command.submitted_at,
            metadata=command.metadata,
            actor_type=command.actor_type,
            client=command.client,
            warnings=[],
        )

    def _record_submission(
        self,
        *,
        application: dict,
        submission_type: str,
        approved_revision_id: str | None,
        artifact_version_id: str | None,
        submitted_at: str,
        metadata: dict,
        actor_type: Literal["user", "system"],
        client: Literal["web", "cli", "worker"],
        warnings: list[str],
    ) -> SubmissionResult:
        application_id = application["id"]
        current = ApplicationStatus(application["current_status"])
        submission_id = new_id()
        event_id: str | None = None
        try:
            with self.repo.unit_of_work() as uow:
                transaction = self.repo.bind(uow)
                transaction.insert_submission(
                    submission_id,
                    application_id,
                    submission_type,
                    approved_revision_id,
                    artifact_version_id,
                    submitted_at,
                    metadata,
                )
                if current is ApplicationStatus.SAVED:
                    event_id = transaction.insert_recruitment_event(
                        application_id=application_id,
                        expected_current_status=current.value,
                        target_status=ApplicationStatus.APPLIED.value,
                        event_type="status_transition",
                        reason="submission recorded",
                        actor_type=actor_type,
                        client=client,
                        installation_id=self.installation_id,
                        occurred_at=submitted_at,
                        terminal_outcome=terminal_outcome_after(
                            application.get("terminal_outcome"), ApplicationStatus.APPLIED
                        ),
                    )
                self._audit(
                    transaction,
                    application_id=application_id,
                    action=(
                        "submit_application"
                        if submission_type == "internal"
                        else "record_external_submission"
                    ),
                    entity_type="submission",
                    entity_id=submission_id,
                    actor_type=actor_type,
                    client=client,
                    occurred_at=submitted_at,
                    details={
                        "submission_type": submission_type,
                        "approved_revision_id": approved_revision_id,
                        "artifact_version_id": artifact_version_id,
                    },
                )
                uow.commit()
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        updated = self.repo.get_application(application_id)
        return SubmissionResult(
            application_id=application_id,
            submission_id=submission_id,
            approved_revision_id=approved_revision_id,
            pdf_artifact_version_id=artifact_version_id,
            current_status=updated["current_status"],
            terminal_outcome=updated.get("terminal_outcome"),
            next_action=updated.get("next_action"),
            next_action_date=updated.get("next_action_date"),
            event_id=event_id,
            warnings=warnings,
        )
