"""Generating the working draft: deterministic composition, then optional wording."""

from __future__ import annotations

from dataclasses import dataclass

from .... import __version__
from ....domain.analysis.approval import unresolved_approval_reasons
from ....domain.analysis.gaps import unaccepted_hard_gaps
from ....domain.knowledge import Knowledge
from ....domain.models import DraftDocument, JobAnalysis
from ....domain.validation import validate_draft as run_draft_validation
from ...commands import DraftCommand, DraftResult
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ...ports import DraftRepository, DraftResumeContext
from ..proposals import (
    ProviderEvidence,
    allowed_fact_pool,
    apply_proposed_claims,
    evidence_attached,
    fact_context,
)
from .common import DraftServiceBase


@dataclass(frozen=True)
class PreparedDraft:
    source: DraftDocument
    analysis: JobAnalysis
    plan_id: str
    knowledge: Knowledge
    evidence: ProviderEvidence | None = None


@dataclass(frozen=True)
class DeterministicRun:
    """What produced a draft when no provider was involved.

    `none` rather than a contract and prompt version, which is what this record
    carried before Stage G. The deterministic composer runs under no AI task
    contract and reads no prompt, so naming one was a value the run never had -
    and it was typed in beside a contract file nothing read, so it could not
    even be wrong consistently. The column is `NOT NULL`, so the honest answer
    is a literal that says there was none.
    """

    provider: str = "deterministic"
    model: str = "rules-v1"
    task_contract_version: str = "none"
    prompt_version: str = "none"


class DraftGeneration(DraftServiceBase):
    """§13: build the working draft from one analysis and one SelectionPlan."""

    def draft(self, command: DraftCommand) -> DraftResult:
        """Build the working draft from one exact analysis.

        The analysis is named by the caller for the same reason the snapshot is
        in `analyze`: a command that resolves `latest` itself can draft from an
        analysis the caller never saw.
        """
        prepared = self.prepare(command)
        return self.activate(command, prepared)

    def prepare(self, command: DraftCommand, *, operation_id: str | None = None) -> PreparedDraft:
        """Build and validate the inputs for a draft without changing durable state.

        `operation_id` is required in AI mode and unused otherwise: it is where
        the sanitized provider response is preserved. The deterministic branch
        never reaches a provider, which is what keeps generation working with
        `OPENAI_API_KEY` unset.
        """
        knowledge = self.load_knowledge()
        profiles, policies = knowledge.profiles, knowledge.policies
        analysis_id = command.job_analysis_id
        try:
            record = self.repo.get_analysis(analysis_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job analysis: {analysis_id}") from exc
        if record["application_id"] != command.application_id:
            raise LineageBroken(
                f"analysis {analysis_id} does not belong to application {command.application_id}"
            )
        try:
            plan = self.repo.selection_plan(command.selection_plan_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown selection plan: {command.selection_plan_id}") from exc
        if plan.application_id != command.application_id or plan.job_analysis_id != analysis_id:
            raise LineageBroken(
                f"selection plan {plan.id} does not belong to application "
                f"{command.application_id} and analysis {analysis_id}"
            )
        if command.parent_revision_id is not None:
            try:
                parent = self.repo.approved_revision(command.parent_revision_id)
            except UnknownRecord as exc:
                raise UnknownRecord(
                    f"unknown parent approved revision: {command.parent_revision_id}"
                ) from exc
            if parent.application_id != command.application_id:
                raise LineageBroken(
                    f"approved revision {parent.id} does not belong to application "
                    f"{command.application_id}"
                )
        # The plan froze the knowledge it selected under. Re-using it against a
        # changed Profile or selection policy would re-derive the sectioning from
        # knowledge the plan never saw, so the draft would not be the plan's
        # decision. Section 4.3 replaces this refusal with a stale reason; until
        # then it fails closed.
        if plan.profile_version != profiles.version:
            raise StateConflict(
                f"selection plan {plan.id} froze profile version {plan.profile_version}, "
                f"but knowledge now reports {profiles.version}; analyze again to obtain a "
                "plan for the current Profile"
            )
        if plan.selection_policy_version != policies.version:
            raise StateConflict(
                f"selection plan {plan.id} froze selection policy version "
                f"{plan.selection_policy_version}, but knowledge now reports "
                f"{policies.version}; analyze again to obtain a plan for the current "
                "selection policy"
            )
        analysis = record["analysis"]
        if analysis.fit.value == "low" and analysis.user_override.get("fit") != "accepted-low-fit":
            raise StateConflict("low fit blocks CV generation until --accept-low-fit is recorded")
        unresolved = unresolved_approval_reasons(analysis)
        if unresolved:
            raise StateConflict(
                "ambiguous classification requires an explicit Track/Profile override: "
                f"{unresolved}"
            )
        # The same question the state projection answers, asked last for the
        # same reason it is reported last: not knowing what the job is outranks
        # not having decided about one of its requirements. This check used to
        # be absent here, so a direct API call could draft, validate and approve
        # a CV the projection reported as blocked.
        blocking = unaccepted_hard_gaps(analysis, plan, job_analysis_id=plan.job_analysis_id)
        if blocking:
            raise StateConflict(
                "hard requirement gaps block CV generation until each is explicitly "
                f"accepted: {[gap.requirement for gap in blocking]}"
            )
        # The draft is built from the analysis's own snapshot, never from whichever
        # snapshot is newest: a job snapshot added after the analysis describes a
        # job nothing has analyzed yet. `latest_snapshot` is read as a staleness
        # check on the named analysis, not to choose what to draft from.
        try:
            latest_snapshot = self.repo.latest_snapshot(command.application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        if record["job_snapshot_id"] != latest_snapshot["id"]:
            raise StateConflict(
                f"job snapshot {latest_snapshot['id']} is newer than the analysis in hand; "
                "analyze the new snapshot before drafting against it"
            )
        draft = self._compose(
            application_id=command.application_id,
            job_snapshot_id=record["job_snapshot_id"],
            job_analysis_id=analysis_id,
            analysis=analysis,
            plan=plan,
            knowledge=knowledge,
        )
        evidence: ProviderEvidence | None = None
        if command.provider == "openai":
            if operation_id is None:
                raise PreconditionFailed(
                    "AI generation runs as an Operation; there is no synchronous form"
                )
            draft, evidence = self._propose_wording(
                command.application_id, operation_id, draft, analysis, knowledge
            )
        return PreparedDraft(
            source=draft,
            analysis=analysis,
            plan_id=plan.id,
            knowledge=knowledge,
            evidence=evidence,
        )

    def _propose_wording(
        self,
        application_id: str,
        operation_id: str,
        draft: DraftDocument,
        analysis: JobAnalysis,
        knowledge: Knowledge,
    ) -> tuple[DraftDocument, ProviderEvidence]:
        """`draft_resume`: ask for wording over a document the engine composed.

        The provider never decides *which* facts appear - the SelectionPlan
        already did, and the document handed to it is the plan's own. It
        proposes how the selected facts are worded, and every line comes back
        through `apply_claim_edit`. Wording its own facts do not support is
        refused as `ProposalRejected`, not saved as a pending claim: §14's
        pending rule is for a person mid-edit, not for a wrong answer.
        """
        profile = knowledge.profiles.get(analysis.profile)
        allowed = allowed_fact_pool(profile)
        selected = sorted(
            {
                fact_id
                for section in draft.sections
                for claim in section.claims
                for fact_id in claim.fact_ids
            }
        )
        answered = self.provider.draft_resume(
            DraftResumeContext(
                job_analysis={
                    "track": analysis.track.value,
                    "profile": analysis.profile.value,
                    "emphasis": analysis.emphasis.value,
                    "language": analysis.language,
                    "keywords": list(analysis.keywords),
                },
                language=draft.language,
                sections=[
                    {
                        "section": section.name,
                        "claims": [
                            {
                                "claim_id": claim.claim_id,
                                "text": claim.text,
                                "fact_ids": list(claim.fact_ids),
                            }
                            for claim in section.claims
                        ],
                    }
                    for section in draft.sections
                ],
                allowed_facts=fact_context(knowledge.facts, selected, draft.language),
            )
        )
        evidence = self.preserve(application_id, operation_id, "draft_resume", answered.provenance)
        del allowed
        with evidence_attached(evidence):
            updated = apply_proposed_claims(
                draft,
                answered.proposal.claims,
                knowledge.facts,
                set(selected),
                task="draft_resume",
            )
        return updated, evidence

    def activate(
        self,
        command: DraftCommand,
        prepared: PreparedDraft,
        repository: DraftRepository | None = None,
    ) -> DraftResult:
        """Commit a prepared WorkingDraft after the final optimistic check."""
        repo = repository or self.repo
        knowledge = prepared.knowledge
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        analysis = prepared.analysis
        profile = profiles.get(analysis.profile)
        presentation_rules = knowledge.presentations
        # §14: a replacement addresses the exact draft version it named; a first draft
        # names none and creates the active record.
        working = repo.replace_active_working_draft(
            command.application_id,
            command.job_analysis_id,
            prepared.plan_id,
            prepared.source,
            parent_revision_id=command.parent_revision_id,
            expected_working_draft_id=command.replaces_working_draft_id,
            expected_edit_version=command.replaces_expected_edit_version,
        )
        stored = self.store_working_draft(working.source)
        report = run_draft_validation(
            working.source,
            stored.markdown,
            facts,
            profile,
            analysis,
            plan=repo.selection_plan(prepared.plan_id),
            policies=policies,
            presentations=presentation_rules,
        )
        repo.record_validation(
            command.application_id,
            "pre-render",
            report,
            lineage=self._lineage(working, knowledge),
        )
        # One source for the three version strings. The deterministic branch
        # names its own engine and the contract file it ran under; the AI branch
        # names the provider execution that produced the wording. Neither is
        # typed in here, which is what stopped the file from disagreeing with
        # the record.
        run_context = (
            prepared.evidence.provenance.context
            if prepared.evidence is not None
            else self._deterministic_run_context()
        )
        repo.record_generation_run(
            {
                "application_id": command.application_id,
                "engine_version": __version__,
                "profile_version": profiles.version,
                "rendering_rules_version": (
                    f"1.0.0+presentations.{presentation_rules.version[:12]}"
                    if presentation_rules is not None
                    else "1.0.0"
                ),
                "facts_version": facts.version,
                "ai_provider": run_context.provider,
                "ai_model": run_context.model,
                "task_contract_version": run_context.task_contract_version,
                "prompt_version": run_context.prompt_version,
                "job_analysis_version": analysis.analysis_version,
                "instruction_overrides": analysis.user_override,
                "status": "completed" if report.passed else "validation-failed",
            }
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
