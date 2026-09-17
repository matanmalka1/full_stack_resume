"""Keep-before-visibility orchestration for working-draft replacement."""

from __future__ import annotations

from ....util import new_id
from ...commands import DraftCommand, ReplaceWorkingDraftCommand
from ...errors import UnknownRecord
from ...operations import OperationView, as_operation_view
from ...ports.idempotency import IdempotencyStore
from ...ports.operation_client import OperationClientStore
from ...ports.transactions import TransactionManager
from ..drafts import DraftAuthoringService
from ..drafts.history import DraftHistoryService
from .service import OperationSubmissionService


class OperationReplacementService:
    """Settle replay, preserve the old draft when requested, then expose work."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        operations: OperationClientStore,
        receipts: IdempotencyStore,
        submissions: OperationSubmissionService,
        draft_history: DraftHistoryService,
    ):
        self.transactions = transactions
        self.operations = operations
        self.receipts = receipts
        self.submissions = submissions
        self.draft_history = draft_history

    def submit_replacement_draft(
        self,
        command: ReplaceWorkingDraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftAuthoringService,
    ) -> OperationView:
        draft_command = DraftCommand(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            selection_plan_id=command.selection_plan_id,
            provider=command.provider,
            replaces_working_draft_id=command.working_draft_id,
            replaces_expected_edit_version=command.expected_edit_version,
            replaces_keep_previous=command.keep_previous,
        )
        with self.transactions.write() as tx:
            receipt = self.receipts.claim_idempotency_receipt(
                tx,
                "replace_working_draft",
                idempotency_key,
                draft_command.model_dump(mode="json"),
                reserved_entity_id=new_id(),
            )
        operation_id = receipt["reserved_entity_id"]
        if receipt["status"] == "completed":
            with self.transactions.read() as tx:
                return as_operation_view(self.operations.operation(tx, operation_id))

        try:
            with self.transactions.read() as tx:
                existing = self.operations.operation(tx, operation_id)
        except UnknownRecord:
            existing = None
        if existing is not None:
            with self.transactions.write() as tx:
                self.receipts.complete_idempotency_receipt(
                    tx, receipt["id"], {"operation_id": existing.id}
                )
            return as_operation_view(existing)

        # Payload materialization and verification deliberately happen outside a DB
        # scope. The history service makes Keep an idempotent ensure, so recovery from
        # a crash here can resume without duplicating the immutable snapshot.
        self.draft_history.prepare_replacement(command)
        queued = self.submissions.submit_draft(
            draft_command,
            idempotency_key=idempotency_key,
            draft_service=draft_service,
            operation_id=operation_id,
        )
        with self.transactions.write() as tx:
            self.receipts.complete_idempotency_receipt(
                tx, receipt["id"], {"operation_id": queued.id}
            )
        return queued
