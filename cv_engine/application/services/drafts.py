from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ... import __version__
from ...domain.analysis.approval import unresolved_approval_reasons
from ...domain.draft_markdown import serialize_markdown, synchronize_markdown_claims
from ...domain.drafts import (
    apply_claim_edit,
    build_draft,
    draft_claims,
    manually_edited,
    seal_draft,
)
from ...domain.knowledge import Knowledge
from ...domain.models import (
    AuditRecord,
    DecisionRecord,
    DraftDocument,
    JobAnalysis,
    ProposedClaim,
    SelectionPlan,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
)
from ...domain.validation import validate_draft as run_draft_validation
from ...util import canonical_json, new_id, sha256_text, utc_now
from ..commands import (
    ApplySelectionChangeCommand,
    ApprovalResult,
    ApproveDraftCommand,
    ArchivedWorkingDraftResult,
    ArchiveWorkingDraftCommand,
    CreateSelectionPlanCommand,
    DecisionMarkdownExport,
    DraftCommand,
    DraftResult,
    EditResult,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RegenerationResult,
    ReplaceWorkingDraftCommand,
    SelectionChangeResult,
    UpdateWorkingDraftCommand,
    ValidateDraftCommand,
    ValidationRunResult,
    WorkingDraftUpdateResult,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    VALIDATION_STALE,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    ProposalRejected,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ..ports import (
    DraftRepository,
    DraftResumeContext,
    PreparationRepository,
    RegenerateClaimContext,
    RegenerateSectionContext,
    SnapshotPayload,
)
from .analysis import AnalysisService
from .base import ServiceBase, bound_analysis, working_draft_record
from .proposals import (
    ProviderEvidence,
    allowed_fact_pool,
    apply_proposed_claims,
    evidence_attached,
    fact_context,
)


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


@dataclass(frozen=True)
class PreparedRegeneration:
    """One accepted regeneration, computed but not yet committed.

    The document already carries the proposed wording: it passed
    `apply_proposed_claims`, which is the same authority a manual edit passes,
    so anything unsupported was refused before this value could exist. What is
    left is the optimistic commit against the exact version that was frozen.
    """

    working: WorkingDraft
    source: DraftDocument
    claim_ids: list[str]
    evidence: ProviderEvidence


class DraftService(ServiceBase[DraftRepository]):
    """The working draft: generation, manual edits, validation, approval."""

    @staticmethod
    def _lineage(working: WorkingDraft, knowledge: Knowledge) -> ValidationRunLineage:
        return ValidationRunLineage(
            working_draft_id=working.id,
            edit_version=working.edit_version,
            content_hash=working.content_hash,
            job_snapshot_id=working.source.job_snapshot_id,
            job_analysis_id=working.job_analysis_id,
            selection_plan_id=working.selection_plan_id,
            knowledge_context_hash=sha256_text(canonical_json(knowledge.versions())),
            validator_versions={"draft": "2.0"},
        )

    @staticmethod
    def _compose(
        *,
        application_id: str,
        job_snapshot_id: str,
        job_analysis_id: str,
        analysis: JobAnalysis,
        plan: SelectionPlan,
        knowledge: Knowledge,
    ) -> DraftDocument:
        """The deterministic document one analysis and one plan produce.

        Shared by generation and by `apply_selection_change`, which has to
        rebuild the same document against a different plan. A second call to
        `build_draft` with its own argument list is how the two would drift.
        """
        try:
            return build_draft(
                application_id=application_id,
                job_snapshot_id=job_snapshot_id,
                job_analysis_id=job_analysis_id,
                analysis=analysis,
                profile=knowledge.profiles.get(analysis.profile),
                facts=knowledge.facts,
                policies=knowledge.policies,
                candidate=knowledge.candidate,
                presentations=knowledge.presentations,
                selection=plan.plan,
            )
        except ValueError as exc:
            raise PreconditionFailed(f"draft could not be built: {exc}") from exc

    def _working(self, working_draft_id: str, expected_version: int) -> WorkingDraft:
        """One exact draft version, named by ID, or the refusal that says why.

        The version is checked here rather than only in the UPDATE clause so a
        read-only command - validate, above all - refuses a stale client with
        the same `409` a save would, instead of quietly reporting on content the
        client is no longer looking at.
        """
        try:
            working = self.repo.working_draft(working_draft_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown working draft: {working_draft_id}") from exc
        if not working.active:
            raise PreconditionFailed(
                f"working draft {working_draft_id} is no longer the active draft"
            )
        if working.edit_version != expected_version:
            raise StateConflict(
                f"working draft {working_draft_id} is at edit version "
                f"{working.edit_version}, not {expected_version}"
            )
        return working

    def _commit_edit(self, working: WorkingDraft, source: DraftDocument) -> WorkingDraft:
        changed = self.repo.update_working_draft(
            working.id,
            working.edit_version,
            source,
        )
        return changed

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
        working = repo.replace_active_working_draft(
            command.application_id,
            command.job_analysis_id,
            prepared.plan_id,
            prepared.source,
        )
        stored = self.store_working_draft(working.source)
        report = run_draft_validation(
            working.source,
            stored.markdown,
            facts,
            profile,
            analysis,
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

    def _require_synced_projection(self, application_id: str, draft: DraftDocument) -> None:
        """Refuse to approve while the projection holds edits SQLite has not imported.

        SQLite is authoritative from boundary 2a, and approval rebuilds the
        projection from it, so an unimported file edit would be destroyed without
        a word. `validate` deliberately reports on the stored draft instead of
        refusing, because that report is true; approval is the trust boundary and
        the point of loss, so the refusal belongs here. The edit is never touched:
        the user imports it with `cv sync-draft` or discards it by regenerating.
        """
        stored = self.working_markdown(application_id)
        if stored and stored != serialize_markdown(draft):
            raise StateConflict(
                "the working Markdown projection differs from the stored draft; "
                "import it with 'cv sync-draft' or regenerate the draft to discard it"
            )

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

    def edit_claim(
        self,
        application_id: str,
        claim_id: str,
        fact_ids: list[str],
        *,
        text: str | None = None,
        template_id: str | None = None,
        template_version: str | None = None,
    ) -> EditResult:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        working = working_draft_record(self.repo, application_id)
        draft = working.source
        _, analysis = bound_analysis(self.repo, application_id, draft, profiles, facts)
        try:
            updated = apply_claim_edit(
                draft,
                claim_id,
                fact_ids,
                facts,
                text=text,
                template_id=template_id,
                template_version=template_version,
            )
        except KeyError as exc:
            raise UnknownRecord(f"unknown claim in the working draft: {claim_id}") from exc
        except ValueError as exc:
            raise PreconditionFailed(f"claim edit rejected: {exc}") from exc
        changed = self._commit_edit(working, updated)
        stored = self.store_working_draft(changed.source)
        report = run_draft_validation(
            changed.source,
            stored.markdown,
            facts,
            profiles.get(updated.profile),
            analysis,
            policies=policies,
            presentations=knowledge.presentations,
        )
        self.repo.record_validation(
            application_id,
            "manual-claim-edit",
            report,
            lineage=self._lineage(changed, knowledge),
        )
        return EditResult(
            application_id=application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            validation=report,
        )

    def link_claim(
        self, application_id: str, claim_id: str, text: str, fact_ids: list[str]
    ) -> EditResult:
        return self.edit_claim(application_id, claim_id, fact_ids, text=text)

    def sync_working_claims(self, application_id: str) -> EditResult:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        working = working_draft_record(self.repo, application_id)
        draft = working.source
        _, analysis = bound_analysis(self.repo, application_id, draft, profiles, facts)
        try:
            updated = synchronize_markdown_claims(
                draft, self.working_markdown(application_id), facts
            )
        except ValueError as exc:
            raise PreconditionFailed(f"working draft synchronization rejected: {exc}") from exc
        changed = self._commit_edit(working, updated)
        stored = self.store_working_draft(changed.source)
        report = run_draft_validation(
            changed.source,
            stored.markdown,
            facts,
            profiles.get(updated.profile),
            analysis,
            policies=policies,
            presentations=knowledge.presentations,
        )
        self.repo.record_validation(
            application_id,
            "manual-markdown-sync",
            report,
            lineage=self._lineage(changed, knowledge),
        )
        return EditResult(
            application_id=application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            validation=report,
        )

    def update_working_draft(self, command: UpdateWorkingDraftCommand) -> WorkingDraftUpdateResult:
        """§14 autosave: apply one structured patch to one exact draft version.

        The whole patch commits as a single edit. Applying each claim as its own
        version would hand the client a version it never asked about and make a
        half-applied patch indistinguishable from a completed one.

        Nothing here validates. §15 owns ValidationRuns, and a run recorded on
        every keystroke would fill the record with evidence nobody asked for and
        make `validated` mean "recently saved" instead of "recently checked".
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        if working.content_hash != command.expected_content_hash:
            raise StateConflict(
                f"working draft {working.id} has content hash {working.content_hash}, "
                f"not {command.expected_content_hash}"
            )
        knowledge = self.load_knowledge()
        facts, profiles = knowledge.facts, knowledge.profiles
        # The chain is checked before the edit, on the same terms as every other
        # path that consumes a draft, so a draft whose lineage no longer holds is
        # refused while nothing has been written.
        bound_analysis(self.repo, working.application_id, working.source, profiles, facts)
        patched = working.source
        for edit in command.claim_edits:
            try:
                patched = apply_claim_edit(
                    patched,
                    edit.claim_id,
                    list(edit.fact_ids),
                    facts,
                    text=edit.text,
                    template_id=edit.template_id,
                    template_version=edit.template_version,
                )
            except KeyError as exc:
                raise UnknownRecord(f"unknown claim in the working draft: {edit.claim_id}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim edit rejected: {exc}") from exc
        changed = self._commit_edit(working, patched)
        self.store_working_draft(changed.source)
        edited = {edit.claim_id for edit in command.claim_edits}
        return WorkingDraftUpdateResult(
            application_id=changed.application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            content_hash=changed.content_hash,
            selection_plan_id=changed.selection_plan_id,
            pending_claim_ids=sorted(
                claim.claim_id
                for claim in draft_claims(changed.source)
                if claim.claim_type == "pending" and claim.claim_id in edited
            ),
        )

    def _regeneration_target(
        self,
        application_id: str,
        working_draft_id: str,
        expected_edit_version: int,
        expected_content_hash: str,
        job_analysis_id: str,
        selection_plan_id: str,
    ) -> tuple[WorkingDraft, Knowledge, JobAnalysis]:
        """The exact draft version a regeneration named, or the refusal that says why.

        All three parts of the draft's identity are checked, plus the analysis
        and plan the client stated. §14 requires regeneration to receive exact
        WorkingDraft ID, version, and hash - so a regeneration launched against
        one version and activated against another is a `409`, not a silent
        overwrite of whatever the draft became in between.
        """
        working = self._working(working_draft_id, expected_edit_version)
        if working.application_id != application_id:
            raise LineageBroken(
                f"working draft {working.id} does not belong to application {application_id}"
            )
        if working.content_hash != expected_content_hash:
            raise StateConflict(
                f"working draft {working.id} has content hash {working.content_hash}, "
                f"not {expected_content_hash}"
            )
        if working.job_analysis_id != job_analysis_id:
            raise LineageBroken(
                f"working draft {working.id} was built from analysis "
                f"{working.job_analysis_id}, not {job_analysis_id}"
            )
        if working.selection_plan_id != selection_plan_id:
            raise LineageBroken(
                f"working draft {working.id} was built from selection plan "
                f"{working.selection_plan_id}, not {selection_plan_id}"
            )
        knowledge = self.load_knowledge()
        record = self.repo.get_analysis(working.job_analysis_id)
        return working, knowledge, record["analysis"]

    def prepare_section_regeneration(
        self,
        command: RegenerateSectionCommand,
        *,
        operation_id: str,
    ) -> PreparedRegeneration:
        """§14 `regenerate_section`: propose replacement wording for one section."""
        working, knowledge, analysis = self._regeneration_target(
            command.application_id,
            command.working_draft_id,
            command.expected_edit_version,
            command.expected_content_hash,
            command.job_analysis_id,
            command.selection_plan_id,
        )
        draft = working.source
        section = next(
            (item for item in draft.sections if item.name == command.section),
            None,
        )
        if section is None:
            raise UnknownRecord(f"unknown section in the working draft: {command.section}")
        allowed = sorted({fact_id for claim in section.claims for fact_id in claim.fact_ids})
        answered = self.provider.regenerate_section(
            RegenerateSectionContext(
                section=section.name,
                language=draft.language,
                job_analysis=self._analysis_context(analysis),
                current_claims=[
                    {
                        "claim_id": claim.claim_id,
                        "text": claim.text,
                        "fact_ids": list(claim.fact_ids),
                    }
                    for claim in section.claims
                ],
                allowed_facts=fact_context(knowledge.facts, allowed, draft.language),
                instruction=command.instruction,
            )
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_section", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.section != section.name:
                raise ProposalRejected(
                    f"regenerate_section answered for section {proposed.section!r}, "
                    f"not {section.name!r}"
                )
            updated = apply_proposed_claims(
                draft,
                proposed.claims,
                knowledge.facts,
                set(allowed),
                task="regenerate_section",
            )
        return PreparedRegeneration(
            working=working,
            source=updated,
            claim_ids=[str(claim.claim_id) for claim in proposed.claims],
            evidence=evidence,
        )

    def prepare_claim_regeneration(
        self,
        command: RegenerateClaimCommand,
        *,
        operation_id: str,
    ) -> PreparedRegeneration:
        """§14 `regenerate_claim`: propose replacement wording for one claim."""
        working, knowledge, analysis = self._regeneration_target(
            command.application_id,
            command.working_draft_id,
            command.expected_edit_version,
            command.expected_content_hash,
            command.job_analysis_id,
            command.selection_plan_id,
        )
        draft = working.source
        located = next(
            (
                (section, claim)
                for section in draft.sections
                for claim in section.claims
                if claim.claim_id == command.claim_id
            ),
            None,
        )
        if located is None:
            raise UnknownRecord(f"unknown claim in the working draft: {command.claim_id}")
        section, claim = located
        allowed = sorted(claim.fact_ids)
        answered = self.provider.regenerate_claim(
            RegenerateClaimContext(
                claim_id=claim.claim_id,
                section=section.name,
                language=draft.language,
                job_analysis=self._analysis_context(analysis),
                current_text=claim.text,
                allowed_facts=fact_context(knowledge.facts, allowed, draft.language),
                instruction=command.instruction,
            )
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_claim", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.claim_id != claim.claim_id:
                raise ProposalRejected(
                    f"regenerate_claim answered for claim {proposed.claim_id!r}, "
                    f"not {claim.claim_id!r}"
                )
            updated = apply_proposed_claims(
                draft,
                [
                    ProposedClaim(
                        section=section.name,
                        claim_id=proposed.claim_id,
                        text=proposed.text,
                        fact_ids=list(proposed.fact_ids),
                    )
                ],
                knowledge.facts,
                set(allowed),
                task="regenerate_claim",
            )
        return PreparedRegeneration(
            working=working,
            source=updated,
            claim_ids=[proposed.claim_id],
            evidence=evidence,
        )

    @staticmethod
    def _analysis_context(analysis: JobAnalysis) -> dict:
        """The narrow analysis view a wording task needs.

        Not the analysis record. Requirements, Fit, approval routing, and
        overrides decide policy, and a task that does not receive them cannot
        be argued into changing them by the job text it is given.
        """
        return {
            "track": analysis.track.value,
            "profile": analysis.profile.value,
            "emphasis": analysis.emphasis.value,
            "language": analysis.language,
            "keywords": list(analysis.keywords),
        }

    def activate_regeneration(
        self,
        prepared: PreparedRegeneration,
        repository: DraftRepository | None = None,
    ) -> RegenerationResult:
        """Commit regenerated wording against the exact version that was frozen.

        The update carries `expected_edit_version`, so a save that happened
        while the Operation ran makes this commit fail rather than overwrite it.
        The provider evidence is registered in the same transaction as the
        wording it produced.
        """
        repo = repository or self.repo
        working = prepared.working
        changed = repo.update_working_draft(
            working.id,
            working.edit_version,
            prepared.source,
        )
        self.store_working_draft(changed.source)
        return RegenerationResult(
            application_id=changed.application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            content_hash=changed.content_hash,
            selection_plan_id=changed.selection_plan_id,
            regenerated_claim_ids=list(prepared.claim_ids),
            provider_artifact_version_id=prepared.evidence.artifact_version_id,
        )

    def apply_selection_change(
        self,
        command: ApplySelectionChangeCommand,
        *,
        analysis_service: AnalysisService,
    ) -> SelectionChangeResult:
        """§14: a deterministic selection change, plan and draft committed together.

        The new SelectionPlan and the draft that is built from it are one write.
        A plan that landed without its draft would be a decision the document
        does not reflect; a draft that landed without its plan would be content
        with no record of what chose it.

        A draft carrying manual wording takes the other branch §14 names. The
        rebuild is deterministic, so it would replace the user's own sentences
        with the engine's without asking - which is the definition of a change
        that needs wording judgment.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        if manually_edited(working.source):
            raise PreconditionFailed(
                "this draft carries manual wording that a deterministic rebuild would "
                "discard; use regenerate_section or regenerate_claim to change its "
                "selection"
            )
        knowledge = self.load_knowledge()
        record = self.repo.get_analysis(working.job_analysis_id)
        analysis: JobAnalysis = record["analysis"]
        with self.repo.unit_of_work() as uow:
            transaction = self.repo.bind(uow)
            created = analysis_service.create_selection_plan(
                CreateSelectionPlanCommand(
                    application_id=working.application_id,
                    job_analysis_id=working.job_analysis_id,
                    pinned_fact_ids=list(command.pinned_fact_ids),
                    excluded_fact_ids=list(command.excluded_fact_ids),
                ),
                cast(PreparationRepository, transaction),
            )
            source = self._compose(
                application_id=working.application_id,
                job_snapshot_id=record["job_snapshot_id"],
                job_analysis_id=working.job_analysis_id,
                analysis=analysis,
                plan=created.plan,
                knowledge=knowledge,
            )
            changed = transaction.update_working_draft(
                working.id,
                working.edit_version,
                source,
                selection_plan_id=created.selection_plan_id,
            )
            uow.commit()
        self.store_working_draft(changed.source)
        return SelectionChangeResult(
            application_id=changed.application_id,
            working_draft_id=changed.id,
            edit_version=changed.edit_version,
            content_hash=changed.content_hash,
            selection_plan_id=changed.selection_plan_id,
            plan=created.plan,
        )

    def materialize_draft_snapshot(self, working: WorkingDraft) -> SnapshotPayload:
        """Write one WorkingDraft version as an immutable historical payload.

        Filesystem first, registration second, exactly as approval does: a
        registration that fails afterwards leaves a reconcilable orphan, whereas
        a pointer written before its payload would name content that does not
        exist.
        """
        _sealed, _markdown, structured_json = seal_draft(working.source)
        try:
            return self.revision_payloads.commit_draft_snapshot(
                working.application_id,
                working.id,
                working.edit_version,
                structured_json,
            )
        except FileExistsError as exc:
            raise StateConflict(
                f"working draft {working.id} version {working.edit_version} "
                f"is already archived: {exc}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not archive the working draft: {exc}") from exc

    def register_draft_snapshot(
        self,
        working: WorkingDraft,
        payload: SnapshotPayload,
        repository: DraftRepository,
    ) -> str:
        """Register one archived draft payload as an immutable artifact version."""
        draft = working.source
        return repository.register_artifact_version(
            working.application_id,
            "working_draft_snapshot",
            "working-draft",
            payload.reference,
            payload.sha256,
            "archived",
            job_snapshot_id=draft.job_snapshot_id,
            track=draft.track.value,
            profile=draft.profile.value,
            emphasis=draft.emphasis.value,
            facts_version=draft.fact_store_version,
            metadata={
                "working_draft_id": working.id,
                "edit_version": working.edit_version,
                "content_hash": working.content_hash,
                "job_analysis_id": working.job_analysis_id,
                "selection_plan_id": working.selection_plan_id,
            },
        )

    def archive_working_draft(
        self, command: ArchiveWorkingDraftCommand
    ) -> ArchivedWorkingDraftResult:
        """§14: register the historical snapshot, then clear the active pointer.

        The order is the contract. The pointer is cleared in the same
        transaction as the registration, so the Application never reaches a
        state where the draft is gone and nothing records what it said.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        payload = self.materialize_draft_snapshot(working)
        now = utc_now()
        with self.repo.unit_of_work() as uow:
            transaction = self.repo.bind(uow)
            artifact_version_id = self.register_draft_snapshot(working, payload, transaction)
            transaction.deactivate_working_draft(working.id, working.edit_version)
            transaction.insert_audit(
                AuditRecord(
                    id=new_id(),
                    application_id=working.application_id,
                    action="archive_working_draft",
                    entity_type="working_draft",
                    entity_id=working.id,
                    actor_type=command.actor_type,
                    client=command.client,
                    installation_id=self.installation_id,
                    occurred_at=now,
                    details={
                        "artifact_version_id": artifact_version_id,
                        "edit_version": working.edit_version,
                    },
                )
            )
            transaction.record_event(
                working.application_id,
                "working_draft_archived",
                {
                    "working_draft_id": working.id,
                    "edit_version": working.edit_version,
                    "artifact_version_id": artifact_version_id,
                },
            )
            uow.commit()
        return ArchivedWorkingDraftResult(
            application_id=working.application_id,
            working_draft_id=working.id,
            edit_version=working.edit_version,
            content_hash=working.content_hash,
            artifact_version_id=artifact_version_id,
        )

    def prepare_replacement(self, command: ReplaceWorkingDraftCommand) -> WorkingDraft:
        """§14: take the Keep decision before anything is replaced.

        Replacement itself is the draft Operation, which commits the new
        document over the same active record in one write - so nothing is
        deleted before the replacement succeeds, and a failed Operation leaves
        the existing draft exactly as it was. What has to happen first is Keep:
        the historical snapshot is materialized here, and it stays true whether
        or not the replacement that follows it succeeds.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        if working.application_id != command.application_id:
            raise LineageBroken(
                f"working draft {working.id} does not belong to application "
                f"{command.application_id}"
            )
        if not command.keep_previous:
            return working
        payload = self.materialize_draft_snapshot(working)
        with self.repo.unit_of_work() as uow:
            transaction = self.repo.bind(uow)
            artifact_version_id = self.register_draft_snapshot(working, payload, transaction)
            transaction.insert_audit(
                AuditRecord(
                    id=new_id(),
                    application_id=working.application_id,
                    action="replace_working_draft",
                    entity_type="working_draft",
                    entity_id=working.id,
                    actor_type=command.actor_type,
                    client=command.client,
                    installation_id=self.installation_id,
                    occurred_at=utc_now(),
                    details={
                        "artifact_version_id": artifact_version_id,
                        "edit_version": working.edit_version,
                        "kept": True,
                    },
                )
            )
            uow.commit()
        return working

    def _require_binding_validation(
        self, working: WorkingDraft, validation_run_id: str, knowledge: Knowledge
    ) -> None:
        """§15's four binding conditions, checked against a run approval did not create.

        This is the whole point of taking the run ID as an argument. While
        approval validated for itself, the four checks compared a run against
        the draft that had just produced it, so they could not fail and proved
        nothing. Against a run the user obtained earlier they are real: an edit
        after validation moves the version, a re-seal moves the hash, and a run
        from another draft names another draft.
        """
        try:
            lineage = self.repo.validation_lineage(validation_run_id)
            report = self.repo.validation_report(validation_run_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown validation run: {validation_run_id}") from exc
        mismatched = [
            name
            for name, recorded, current in (
                ("working draft", lineage.working_draft_id, working.id),
                ("edit version", lineage.edit_version, working.edit_version),
                ("content hash", lineage.content_hash, working.content_hash),
                (
                    "knowledge context",
                    lineage.knowledge_context_hash,
                    sha256_text(canonical_json(knowledge.versions())),
                ),
            )
            if recorded != current
        ]
        if mismatched:
            raise PreconditionFailed(
                f"validation run {validation_run_id} does not describe the draft being "
                f"approved: {', '.join(mismatched)} differs; validate again",
                code=VALIDATION_STALE,
            )
        if not report.passed:
            raise ValidationBlocked("approval blocked by pre-render validation", report)

    def approve_draft(
        self, command: ApproveDraftCommand, *, revision_id: str | None = None
    ) -> ApprovalResult:
        """§15: approve exactly the content one named ValidationRun passed.

        No validation runs here. Approval consumes evidence; it does not
        manufacture it.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        application_id = working.application_id
        quarantined = self.repo.quarantined_knowledge_mutations()
        if quarantined:
            raise PreconditionFailed(
                f"approval blocked by quarantined Knowledge mutation {quarantined[0].id}"
            )
        self._require_synced_projection(application_id, working.source)
        knowledge = self.load_knowledge()
        self._require_binding_validation(working, command.validation_run_id, knowledge)
        validation_id = command.validation_run_id
        facts, profiles = knowledge.facts, knowledge.profiles
        draft = working.source
        # SQLite is authoritative. Seal the exact stored document and commit its
        # immutable payloads before any revision row can become visible.
        sealed, markdown, structured_json = seal_draft(draft)
        if sealed.content_hash != working.content_hash:
            raise StateConflict("working draft content hash changed before approval")
        # The decision record explains the draft being approved, so it is bound to
        # that draft's own analysis. A newer analysis does not get to describe an
        # older document.
        analysis_id, analysis = bound_analysis(self.repo, application_id, draft, profiles, facts)
        revision_id = revision_id or new_id()
        try:
            published = self.revision_payloads.commit_revision(
                application_id,
                revision_id,
                structured_json,
                markdown,
            )
        except FileExistsError as exc:
            raise StateConflict(str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not publish approved revision: {exc}") from exc
        if published.structured.sha256 != sha256_text(
            structured_json
        ) or published.markdown.sha256 != sha256_text(markdown):
            raise InfrastructureFailure("approved revision payload hash verification failed")

        now = utc_now()
        recruiter_pdf_filename = self.renderer.filename_for(
            profiles.get(draft.profile).normalized_role, self.candidate()
        )
        application = self.repo.get_application(application_id)
        structured = {
            "company": application["company"],
            "target_job": application["target_role"],
            "track": draft.track.value,
            "profile": draft.profile.value,
            "emphasis": draft.emphasis.value,
            "confidence": analysis.confidence,
            "rationale": analysis.rationale,
            "fit": analysis.fit.value,
            "gaps": [gap.model_dump(mode="json") for gap in analysis.gaps],
            "selected_fact_ids": draft.selected_fact_ids,
            "omitted_facts": draft.omitted_facts,
            "derived_statements": [
                claim.model_dump(mode="json")
                for section in draft.sections
                for claim in section.claims
                if claim.claim_type in {"composite", "derived"}
            ],
            "accepted_warnings_or_gaps": analysis.user_override,
            "user_overrides": analysis.user_override,
            "fact_store_version": facts.version,
            "job_snapshot_id": draft.job_snapshot_id,
            "job_analysis_id": analysis_id,
            "artifact_paths": {
                "markdown": published.markdown.reference,
            },
            "recruiter_pdf_filename": recruiter_pdf_filename,
        }
        decision_summary = (
            f"Approved {draft.profile.value} / {draft.emphasis.value} CV for "
            f"{application['company']}."
        )
        decision_provenance = {
            "actor_type": command.actor_type,
            "client": command.client,
            "command": "approve_draft",
            "installation_id": self.installation_id,
        }
        with self.repo.unit_of_work() as uow:
            transaction = self.repo.bind(uow)
            revision = transaction.create_approved_revision(
                application_id,
                revision_id,
                working.id,
                validation_id,
                published.structured.reference,
                published.structured.sha256,
                published.markdown.reference,
                published.markdown.sha256,
                decision_provenance,
                approved_at=now,
            )
            markdown_version_id = transaction.register_artifact_version(
                application_id,
                "resume_markdown",
                "resume",
                published.markdown.reference,
                published.markdown.sha256,
                "approved",
                revision_id=revision.id,
                job_snapshot_id=draft.job_snapshot_id,
                track=draft.track.value,
                profile=draft.profile.value,
                emphasis=draft.emphasis.value,
                facts_version=facts.version,
                approved_at=now,
            )
            # resume.json is one physical payload with two roles: revision-owned
            # structured content and the separately registered claim manifest.
            manifest_version_id = transaction.register_artifact_version(
                application_id,
                "claim_manifest",
                "resume-claims",
                published.structured.reference,
                published.structured.sha256,
                "approved",
                revision_id=revision.id,
                job_snapshot_id=draft.job_snapshot_id,
                track=draft.track.value,
                profile=draft.profile.value,
                emphasis=draft.emphasis.value,
                facts_version=facts.version,
                approved_at=now,
            )
            decision = DecisionRecord(
                id=new_id(),
                application_id=application_id,
                artifact_version_id=markdown_version_id,
                job_snapshot_id=draft.job_snapshot_id,
                job_analysis_id=analysis_id,
                structured=structured,
                summary=decision_summary,
                created_at=now,
            )
            transaction.insert_decision(decision)
            transaction.insert_audit(
                AuditRecord(
                    id=new_id(),
                    application_id=application_id,
                    action="approve_draft",
                    entity_type="approved_revision",
                    entity_id=revision.id,
                    actor_type=command.actor_type,
                    client=command.client,
                    installation_id=self.installation_id,
                    occurred_at=now,
                    details={
                        "decision_record_id": decision.id,
                        "validation_run_id": validation_id,
                    },
                )
            )
            transaction.record_event(
                application_id,
                "draft_approved",
                {
                    "approved_revision_id": revision.id,
                    "decision_record_id": decision.id,
                    "version": revision.version_number,
                },
            )
            uow.commit()
        return ApprovalResult(
            application_id=application_id,
            revision_id=revision.id,
            version=revision.version_number,
            markdown_artifact_version_id=markdown_version_id,
            manifest_artifact_version_id=manifest_version_id,
            decision_record_id=decision.id,
        )

    def export_decision_markdown(
        self, application_id: str, approved_revision_id: str
    ) -> DecisionMarkdownExport:
        """Render human-readable provenance for one explicitly named revision."""
        try:
            application = self.repo.get_application(application_id)
            revision = self.repo.approved_revision(approved_revision_id)
            decision = self.repo.decision_for_revision(approved_revision_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown decision export source: {exc.args[0]}") from exc
        if (
            revision.application_id != application_id
            or decision["application_id"] != application_id
        ):
            raise StateConflict("approved revision belongs to another application")
        import json

        structured = json.loads(decision["structured_json"])
        selected = structured.get("selected_fact_ids") or []
        gaps = structured.get("accepted_warnings_or_gaps") or {}
        overrides = structured.get("user_overrides") or {}

        def value(item: object) -> str:
            if isinstance(item, (dict, list)):
                return json.dumps(item, ensure_ascii=False, sort_keys=True)
            return str(item)

        lines = [
            "# CV Decision and Provenance",
            "",
            f"- Application: {application['company']} — {application['target_role']}",
            f"- Application ID: `{application_id}`",
            f"- Approved revision ID: `{revision.id}`",
            f"- Approved at: {revision.approved_at}",
            f"- Decision record ID: `{decision['id']}`",
            "",
            "## Decision",
            "",
            decision["summary"],
            "",
            "## Classification",
            "",
        ]
        for label, key in (
            ("Track", "track"),
            ("Profile", "profile"),
            ("Emphasis", "emphasis"),
            ("Language", "language"),
            ("Fit", "fit"),
        ):
            lines.append(f"- {label}: {value(structured.get(key, ''))}")
        lines.extend(["", "## Selected facts", ""])
        lines.extend(f"- `{fact_id}`" for fact_id in selected)
        if not selected:
            lines.append("- None recorded")
        lines.extend(
            [
                "",
                "## Accepted gaps and overrides",
                "",
                f"- Accepted warnings or gaps: {value(gaps)}",
                f"- User overrides: {value(overrides)}",
                "",
                "## Exact lineage",
                "",
                f"- Job snapshot ID: `{revision.job_snapshot_id}`",
                f"- Job analysis ID: `{revision.job_analysis_id}`",
                f"- Selection plan ID: `{revision.selection_plan_id}`",
                f"- Working draft ID: `{revision.working_draft_id}`",
                f"- Validation run ID: `{revision.validation_run_id}`",
                f"- Draft content SHA-256: `{revision.draft_content_hash}`",
                f"- Knowledge context SHA-256: `{revision.knowledge_context_hash}`",
                f"- Candidate context SHA-256: `{revision.candidate_context_hash}`",
                f"- Resume JSON SHA-256: `{revision.resume_json_hash}`",
                f"- Resume Markdown SHA-256: `{revision.resume_markdown_hash}`",
                "",
                "## Approval actor",
                "",
            ]
        )
        for key in ("actor_type", "client", "installation_id", "command"):
            lines.append(f"- {key}: {revision.decision_provenance.get(key, '')}")
        content = "\n".join(lines) + "\n"
        return DecisionMarkdownExport(
            application_id=application_id,
            approved_revision_id=approved_revision_id,
            filename=f"decision-{approved_revision_id}.md",
            content=content,
            content_hash=sha256_text(content),
        )
