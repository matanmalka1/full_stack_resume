from __future__ import annotations

from typing import Literal

from ....domain.contracts.records import AuditRecord
from ....domain.contracts.recruitment import ApplicationStatus
from ....domain.recruitment import (
    submission_owns_transition,
    terminal_outcome_after,
    user_transition_allowed,
)
from ....util import new_id, utc_now
from ...commands import (
    ApplicationMutationResult,
    CloseApplicationCommand,
    DeleteApplicationCommand,
    NextActionCommand,
    RecruitmentCorrectionCommand,
    RecruitmentStatusCommand,
    WriteClient,
)
from ...errors import StateConflict, UnknownRecord
from ...ports.application_intake import AuditLogWriter
from ...ports.recruitment import RecruitmentStore
from ...ports.transactions import TransactionManager


class RecruitmentService:
    def __init__(
        self, transactions: TransactionManager, recruitment: RecruitmentStore, audit: AuditLogWriter
    ):
        self._transactions = transactions
        self._recruitment = recruitment
        self._audit_log = audit

    def _application(self, application_id: str, *, active: bool = True) -> dict:
        with self._transactions.read() as tx:
            application = self._recruitment.application(tx, application_id)
        if active and application.get("deleted_at") is not None:
            raise StateConflict(f"application is deleted: {application_id}")
        return application

    def _result(
        self, application_id: str, event_id: str | None = None
    ) -> ApplicationMutationResult:
        application = self._application(application_id, active=False)
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
        tx,
        *,
        application_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        actor_type: Literal["user", "system"],
        client: WriteClient,
        occurred_at: str,
        details: dict | None = None,
    ) -> None:
        self._audit_log.insert_audit(
            tx,
            AuditRecord(
                id=new_id(),
                application_id=application_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_type=actor_type,
                client=client,
                occurred_at=occurred_at,
                details=details or {},
            ),
        )

    def transition_status(self, command: RecruitmentStatusCommand) -> ApplicationMutationResult:
        application = self._application(command.application_id)
        try:
            current, target = (
                ApplicationStatus(application["current_status"]),
                ApplicationStatus(command.target_status),
            )
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        if submission_owns_transition(target):
            raise StateConflict("applied is submission-owned and cannot be set directly")
        if target is current:
            return self._result(command.application_id)
        if not user_transition_allowed(current, target):
            raise StateConflict(f"invalid status transition: {current.value} -> {target.value}")
        now, event_id = command.occurred_at or utc_now(), new_id()
        with self._transactions.write() as tx:
            self._recruitment.insert_event(
                tx,
                application_id=command.application_id,
                expected_current_status=current.value,
                target_status=target.value,
                event_type="status_transition",
                reason=command.reason,
                actor_type=command.actor_type,
                client=command.client,
                occurred_at=now,
                terminal_outcome=terminal_outcome_after(
                    application.get("terminal_outcome"), target
                ),
                event_id=event_id,
            )
            self._audit(
                tx,
                application_id=command.application_id,
                action="transition_recruitment_status",
                entity_type="recruitment_event",
                entity_id=event_id,
                actor_type=command.actor_type,
                client=command.client,
                occurred_at=now,
                details={"from_status": current.value, "to_status": target.value},
            )
        return self._result(command.application_id, event_id)

    def close_application(self, command: CloseApplicationCommand) -> ApplicationMutationResult:
        return self.transition_status(
            RecruitmentStatusCommand(
                application_id=command.application_id,
                target_status="closed",
                reason="application closed",
                actor_type=command.actor_type,
                client=command.client,
            )
        )

    def delete_application(self, command: DeleteApplicationCommand) -> ApplicationMutationResult:
        self._application(command.application_id)
        now = utc_now()
        with self._transactions.write() as tx:
            self._recruitment.set_deleted(tx, command.application_id, now)
            self._audit(
                tx,
                application_id=command.application_id,
                action="delete_application",
                entity_type="application",
                entity_id=command.application_id,
                actor_type=command.actor_type,
                client=command.client,
                occurred_at=now,
            )
        return self._result(command.application_id)

    def correct_recruitment_status(
        self, command: RecruitmentCorrectionCommand
    ) -> ApplicationMutationResult:
        if not command.reason.strip():
            raise StateConflict("recruitment correction reason is required")
        application = self._application(command.application_id)
        try:
            current, target = (
                ApplicationStatus(application["current_status"]),
                ApplicationStatus(command.target_status),
            )
            with self._transactions.read() as tx:
                corrected = self._recruitment.event(tx, command.corrects_event_id)
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown recruitment correction source: {exc.args[0]}") from exc
        if (
            corrected["application_id"] != command.application_id
            or corrected["event_type"] == "next_action"
        ):
            raise StateConflict(
                "a status correction must reference this application's status event"
            )
        now, event_id = command.occurred_at or utc_now(), new_id()
        with self._transactions.write() as tx:
            self._recruitment.insert_event(
                tx,
                application_id=command.application_id,
                expected_current_status=current.value,
                target_status=target.value,
                event_type="status_correction",
                reason=command.reason.strip(),
                actor_type=command.actor_type,
                client=command.client,
                occurred_at=now,
                terminal_outcome=terminal_outcome_after(
                    application.get("terminal_outcome"), target
                ),
                corrects_event_id=command.corrects_event_id,
                event_id=event_id,
            )
            self._audit(
                tx,
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
        return self._result(command.application_id, event_id)

    def set_next_action(self, command: NextActionCommand) -> ApplicationMutationResult:
        self._application(command.application_id)
        now = command.occurred_at or utc_now()
        with self._transactions.write() as tx:
            event_id = self._recruitment.insert_next_action(
                tx,
                application_id=command.application_id,
                next_action=command.next_action,
                next_action_date=command.next_action_date,
                actor_type=command.actor_type,
                client=command.client,
                occurred_at=now,
            )
            self._audit(
                tx,
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
        return self._result(command.application_id, event_id)
