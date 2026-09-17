"""§15: recording what one exact working-draft version validated as."""

from __future__ import annotations

from ....domain.contracts.drafts import WorkingDraft
from ....domain.contracts.validation import ValidationReport
from ....domain.draft_markdown import serialize_markdown
from ....domain.knowledge import Knowledge
from ....domain.validation import validate_draft as run_draft_validation
from ...chain import ChainError, check_loaded_draft_chain
from ...commands import ValidateDraftCommand, ValidationRunResult
from ...errors import LineageBroken, StateConflict, UnknownRecord
from ...ports import KnowledgeStore, TransactionManager
from ...ports.drafts import DraftLifecycleStore, DraftValidationContext, DraftValidationSourceReader
from ...ports.validation_store import ValidationStore
from ..analysis.service import load_analysis_knowledge
from .inputs import require_content_hash, require_working_version, validation_lineage


class DraftValidationService:
    """The pre-render validation run, recorded whether or not it passed."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        drafts: DraftLifecycleStore,
        sources: DraftValidationSourceReader,
        validations: ValidationStore,
        knowledge: KnowledgeStore,
    ):
        self.transactions = transactions
        self.drafts = drafts
        self.sources = sources
        self.validations = validations
        self.knowledge = knowledge

    def validate_draft(self, command: ValidateDraftCommand) -> ValidationRunResult:
        """§15: validate one exact WorkingDraft version, always recording the run.

        `passed=false` is an outcome, not an error: the run is written either
        way, because a failed validation is exactly the evidence the user needs
        and the state projection reads. Only a validator that could not execute
        is a failure, and that surfaces as an infrastructure refusal rather than
        as a report nobody produced.
        """
        with self.transactions.read() as tx:
            try:
                working = self.drafts.working_draft(tx, command.working_draft_id)
            except UnknownRecord as exc:
                raise UnknownRecord(f"unknown working draft: {command.working_draft_id}") from exc
            require_working_version(working, command.expected_edit_version)
            context = self.sources.validation_context(tx, working)
        if context.deleted_at is not None:
            raise StateConflict(f"application is deleted: {working.application_id}")
        knowledge = load_analysis_knowledge(self.knowledge)
        report = self._run_validation(working, knowledge, context)
        with self.transactions.write() as tx:
            current = self.drafts.lock_working_draft(tx, working.id)
            require_working_version(current, working.edit_version)
            require_content_hash(current, working.content_hash)
            validation_id = self.validations.record_validation(
                tx,
                working.application_id,
                "pre-render",
                report,
                lineage=validation_lineage(working, knowledge),
            )
        return ValidationRunResult(
            application_id=working.application_id,
            working_draft_id=working.id,
            validation_run_id=validation_id,
            edit_version=working.edit_version,
            content_hash=working.content_hash,
            passed=report.passed,
            report=report,
        )

    def _run_validation(
        self, working: WorkingDraft, knowledge: Knowledge, context: DraftValidationContext
    ) -> ValidationReport:
        """Validate one loaded draft and record the immutable run for it."""
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        draft = working.source
        chain = check_loaded_draft_chain(
            context.chain, working.application_id, draft, profiles, facts
        )
        try:
            _, analysis = chain.bound()
        except ChainError as exc:
            raise LineageBroken(f"draft chain rejected: {exc}") from exc
        report = run_draft_validation(
            draft,
            serialize_markdown(draft),
            facts,
            profiles.get(draft.profile),
            analysis,
            plan=context.plan,
            policies=policies,
            presentations=knowledge.presentations,
        )
        return report
