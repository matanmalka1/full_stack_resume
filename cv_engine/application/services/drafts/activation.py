from __future__ import annotations

from .... import __version__
from ....domain.draft_markdown import serialize_markdown
from ...commands import DraftCommand, DraftResult, RegenerationResult
from ...ports.analysis_plans import AnalysisPlanStore
from ...ports.drafts import DraftLifecycleStore
from ...ports.transactions import WriteTransaction
from ...ports.validation_store import ValidationStore
from . import generation as generation_checks
from .generation import DeterministicRun, PreparedDraft
from .inputs import validation_lineage
from .regeneration import PreparedRegeneration


class DraftActivation:
    def __init__(
        self, drafts: DraftLifecycleStore, plans: AnalysisPlanStore, validations: ValidationStore
    ):
        self.drafts = drafts
        self.plans = plans
        self.validations = validations

    _lineage = staticmethod(validation_lineage)

    def activate_generation(
        self, tx: WriteTransaction, command: DraftCommand, prepared: PreparedDraft
    ) -> DraftResult:
        """Commit a prepared WorkingDraft after the final optimistic check."""
        knowledge = prepared.knowledge
        facts, profiles, policies = (knowledge.facts, knowledge.profiles, knowledge.policies)
        analysis = prepared.analysis
        profile = profiles.get(analysis.profile)
        presentation_rules = knowledge.presentations
        working = self.drafts.replace_active_working_draft(
            tx,
            command.application_id,
            command.job_analysis_id,
            prepared.plan_id,
            prepared.source,
            parent_revision_id=command.parent_revision_id,
            expected_working_draft_id=command.replaces_working_draft_id,
            expected_edit_version=command.replaces_expected_edit_version,
        )
        report = generation_checks.run_draft_validation(
            working.source,
            serialize_markdown(working.source),
            facts,
            profile,
            analysis,
            plan=self.plans.selection_plan(tx, prepared.plan_id),
            policies=policies,
            presentations=presentation_rules,
        )
        self.validations.record_validation(
            tx,
            command.application_id,
            "pre-render",
            report,
            lineage=self._lineage(working, knowledge),
        )
        run_context = (
            prepared.evidence.provenance.context
            if prepared.evidence is not None
            else self._deterministic_run_context()
        )
        self.drafts.record_generation_run(
            tx,
            {
                "application_id": command.application_id,
                "engine_version": __version__,
                "profile_version": profiles.version,
                "rendering_rules_version": f"1.0.0+presentations.{presentation_rules.version[:12]}"
                if presentation_rules is not None
                else "1.0.0",
                "facts_version": facts.version,
                "ai_provider": run_context.provider,
                "ai_model": run_context.model,
                "task_contract_version": run_context.task_contract_version,
                "prompt_version": run_context.prompt_version,
                "job_analysis_version": analysis.analysis_version,
                "instruction_overrides": analysis.user_override,
                "status": "completed" if report.passed else "validation-failed",
            },
        )
        return DraftResult(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            selection_plan_id=prepared.plan_id,
            working_draft_id=working.id,
            edit_version=working.edit_version,
            validation=report,
        )

    @staticmethod
    def _deterministic_run_context() -> DeterministicRun:
        return DeterministicRun()

    def activate_regeneration(
        self, tx: WriteTransaction, prepared: PreparedRegeneration
    ) -> RegenerationResult:
        """Commit regenerated wording against the exact version that was frozen.

        The update carries `expected_edit_version`, so a save that happened
        while the Operation ran makes this commit fail rather than overwrite it.
        The provider evidence is registered in the same transaction as the
        wording it produced.
        """
        working = prepared.working
        changed = self.drafts.update_working_draft(
            tx, working.id, working.edit_version, prepared.source
        )
        return RegenerationResult(
            application_id=changed.application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            content_hash=changed.content_hash,
            selection_plan_id=changed.selection_plan_id,
            regenerated_claim_ids=list(prepared.claim_ids),
            provider_artifact_version_id=prepared.evidence.artifact_version_id,
        )
