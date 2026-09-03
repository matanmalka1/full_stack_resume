"""§15: recording what one exact working-draft version validated as."""

from __future__ import annotations

from ....domain.draft_markdown import serialize_markdown
from ....domain.knowledge import Knowledge
from ....domain.models import ValidationReport, WorkingDraft
from ....domain.validation import validate_draft as run_draft_validation
from ...commands import ValidateDraftCommand, ValidationRunResult
from ..base import bound_analysis
from .common import DraftServiceBase


class DraftValidation(DraftServiceBase):
    """The pre-render validation run, recorded whether or not it passed."""

    def validate_draft(self, command: ValidateDraftCommand) -> ValidationRunResult:
        """§15: validate one exact WorkingDraft version, always recording the run.

        `passed=false` is an outcome, not an error: the run is written either
        way, because a failed validation is exactly the evidence the user needs
        and the state projection reads. Only a validator that could not execute
        is a failure, and that surfaces as an infrastructure refusal rather than
        as a report nobody produced.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        knowledge = self.load_knowledge()
        report, validation_id = self._run_validation(working, knowledge)
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
        self, working: WorkingDraft, knowledge: Knowledge
    ) -> tuple[ValidationReport, str]:
        """Validate one loaded draft and record the immutable run for it."""
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        draft = working.source
        _, analysis = bound_analysis(self.repo, working.application_id, draft, profiles, facts)
        report = run_draft_validation(
            draft,
            serialize_markdown(draft),
            facts,
            profiles.get(draft.profile),
            analysis,
            plan=self.repo.selection_plan(working.selection_plan_id),
            policies=policies,
            presentations=knowledge.presentations,
        )
        validation_id = self.repo.record_validation(
            working.application_id,
            "pre-render",
            report,
            lineage=self._lineage(working, knowledge),
        )
        return report, validation_id
