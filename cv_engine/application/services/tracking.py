from __future__ import annotations

from ...domain.models import (
    ApplicationStatus,
)
from ...util import new_id, utc_now
from ..commands import (
    ApplicationMutationResult,
    NextActionCommand,
    RecruitmentStatusCommand,
    SubmissionResult,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ..ports import (
    TrackingRepository,
)
from ..ready import qualify_ready_revision
from .base import ServiceBase


class TrackingService(ServiceBase[TrackingRepository]):
    """Recruitment-side state: submission and its evidence."""

    def transition_status(self, command: RecruitmentStatusCommand) -> ApplicationMutationResult:
        try:
            self.repo.transition_status(
                command.application_id, command.target_status, command.reason
            )
            application = self.repo.get_application(command.application_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        return ApplicationMutationResult(
            application_id=command.application_id,
            current_status=application["current_status"],
            next_action=application.get("next_action"),
            next_action_date=application.get("next_action_date"),
        )

    def set_next_action(self, command: NextActionCommand) -> ApplicationMutationResult:
        try:
            self.repo.set_next_action(
                command.application_id,
                command.next_action,
                command.next_action_date,
            )
            application = self.repo.get_application(command.application_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        return ApplicationMutationResult(
            application_id=command.application_id,
            current_status=application["current_status"],
            next_action=application.get("next_action"),
            next_action_date=application.get("next_action_date"),
        )

    def submit(
        self, application_id: str, reason: str = "submitted to employer"
    ) -> SubmissionResult:
        try:
            application = self.repo.get_application(application_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        current = ApplicationStatus(application["current_status"])
        if current not in (ApplicationStatus.PREPARING, ApplicationStatus.READY):
            raise StateConflict("applied requires a currently valid ready application")
        try:
            qualification = qualify_ready_revision(self.artifacts, self.repo, application_id)
        except KeyError as exc:
            raise StateConflict("applied requires a currently valid ready application") from exc
        if not qualification.ready_qualified:
            raise ValidationBlocked(
                "applied blocked by stale or tampered ready state: "
                f"{[issue.code for issue in qualification.validation.issues]}"
            )
        pdf_artifact_version_id = qualification.pdf_artifact_version_id
        if pdf_artifact_version_id is None:
            raise ValidationBlocked("applied blocked because Ready has no exact PDF artifact")
        now = utc_now()
        try:
            with self.repo.unit_of_work() as uow:
                transaction = self.repo.bind(uow)
                transaction.insert_submission(
                    new_id(),
                    application_id,
                    pdf_artifact_version_id,
                    now,
                    {"reason": reason},
                )
                transaction.store_applied_transition(
                    application_id,
                    current,
                    now,
                    reason,
                )
                uow.commit()
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        updated = self.repo.get_application(application_id)
        return SubmissionResult(
            application_id=application_id,
            pdf_artifact_version_id=pdf_artifact_version_id,
            current_status=updated["current_status"],
            next_action=updated.get("next_action"),
            next_action_date=updated.get("next_action_date"),
        )
