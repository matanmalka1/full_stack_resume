from __future__ import annotations

from ....domain.contracts.analysis import JobAnalysis
from ....domain.contracts.drafts import DraftDocument, WorkingDraft
from ....domain.contracts.providers import ProposedClaim
from ....domain.contracts.selection import SelectionPlan
from ....domain.draft_markdown import serialize_markdown
from ....domain.drafts import add_claim, apply_claim_edit, draft_claims, remove_claim, reorder_draft
from ....domain.knowledge import Knowledge
from ....domain.validation import validate_draft as run_draft_validation
from ...chain import ChainError, check_loaded_draft_chain, draft_source_mismatch
from ...commands import (
    DraftCommand,
    DraftResult,
    EditResult,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RegenerationResult,
    UpdateWorkingDraftCommand,
    WorkingDraftUpdateResult,
)
from ...errors import (
    ApplicationError,
    DependencyUnavailable,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    ProposalRejected,
    StateConflict,
    UnknownRecord,
)
from ...ports import (
    AIProvider,
    ArtifactStore,
    AssessClaimSupportContext,
    DraftResumeContext,
    KnowledgeStore,
    RegenerateClaimContext,
    RegenerateSectionContext,
    SnapshotPayloadStore,
    TransactionManager,
)
from ...ports.analysis_plans import AnalysisPlanStore
from ...ports.drafts import DraftAuthoringSourceReader, DraftEvidencePreserver, DraftLifecycleStore
from ...ports.validation_store import ValidationStore
from ..analysis.service import load_analysis_knowledge
from ..proposals import (
    ProviderEvidence,
    apply_proposed_claims,
    authorize_semantically_reviewed_claims,
    evidence_attached,
    fact_context,
)
from .activation import DraftActivation
from .inputs import (
    PreparedDraft,
    PreparedRegeneration,
    compose,
    require_content_hash,
    require_working_version,
    validation_lineage,
)
from .selection import SelectionChangeService


class DraftAuthoringService:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        drafts: DraftLifecycleStore,
        plans: AnalysisPlanStore,
        validations: ValidationStore,
        sources: DraftAuthoringSourceReader,
        knowledge: KnowledgeStore,
        artifacts: ArtifactStore,
        provider: AIProvider | None,
        evidence: DraftEvidencePreserver,
        selection_changes: SelectionChangeService,
        snapshot_payloads: SnapshotPayloadStore | None = None,
    ):
        self.transactions = transactions
        self.drafts = drafts
        self.plans = plans
        self.validations = validations
        self.sources = sources
        self._knowledge = knowledge
        self.artifacts = artifacts
        self._provider = provider
        self.evidence = evidence
        self.selection_changes = selection_changes
        self.snapshot_payloads = snapshot_payloads
        self.activation = DraftActivation(drafts, plans, validations)

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            raise DependencyUnavailable("AI mode was requested but no provider is configured")
        return self._provider

    def load_knowledge(self) -> Knowledge:
        return load_analysis_knowledge(self._knowledge)

    def load_active_application(self, application_id: str) -> None:
        with self.transactions.read() as tx:
            deleted_at = self.sources.deleted_at(tx, application_id)
        if deleted_at is not None:
            raise StateConflict(f"application is deleted: {application_id}")

    def _working(self, working_draft_id: str, expected_version: int) -> WorkingDraft:
        with self.transactions.read() as tx:
            try:
                working = self.drafts.working_draft(tx, working_draft_id)
            except UnknownRecord as exc:
                raise UnknownRecord(f"unknown working draft: {working_draft_id}") from exc
        require_working_version(working, expected_version)
        return working

    def active_working_draft(self, application_id: str) -> WorkingDraft:
        with self.transactions.read() as tx:
            return self.drafts.active_working_draft(tx, application_id)

    def working_draft(self, working_draft_id: str) -> WorkingDraft:
        with self.transactions.read() as tx:
            return self.drafts.working_draft(tx, working_draft_id)

    def _commit_edit(self, working: WorkingDraft, source: DraftDocument) -> WorkingDraft:
        with self.transactions.write() as tx:
            return self.drafts.update_working_draft(tx, working.id, working.edit_version, source)

    def store_working_draft(self, draft: DraftDocument):
        try:
            return self.artifacts.write_working_draft(draft)
        except OSError as exc:
            raise InfrastructureFailure(f"could not store working draft: {exc}") from exc

    def analysis_record(self, analysis_id: str) -> dict:
        with self.transactions.read() as tx:
            return self.sources.analysis_source(tx, analysis_id)

    def selection_plan(self, plan_id: str) -> SelectionPlan:
        with self.transactions.read() as tx:
            return self.plans.selection_plan(tx, plan_id)

    def approved_revision(self, revision_id: str):
        with self.transactions.read() as tx:
            return self.drafts.approved_revision(tx, revision_id)

    def latest_snapshot(self, application_id: str) -> dict:
        with self.transactions.read() as tx:
            return {"id": self.sources.active_snapshot_id(tx, application_id)}

    def snapshot_source(self, snapshot_id: str) -> dict:
        with self.transactions.read() as tx:
            return self.sources.snapshot_source(tx, snapshot_id)

    def bound_analysis(self, application_id, draft, profiles, facts):
        with self.transactions.read() as tx:
            source = self.sources.chain_source(tx, application_id, draft)
        chain = check_loaded_draft_chain(source, application_id, draft, profiles, facts)
        try:
            return chain.bound()
        except ChainError as exc:
            raise LineageBroken(f"draft chain rejected: {exc}") from exc

    def record_validation(self, application_id, stage, report, *, lineage):
        with self.transactions.write() as tx:
            current = self.drafts.lock_working_draft(tx, lineage.working_draft_id)
            if current.application_id != application_id:
                raise LineageBroken(
                    f"working draft {current.id} does not belong to application {application_id}"
                )
            require_working_version(current, lineage.edit_version)
            require_content_hash(current, lineage.content_hash)
            return self.validations.record_validation(
                tx, application_id, stage, report, lineage=lineage
            )

    def preserve(self, application_id, operation_id, task, provenance):
        return self.evidence.preserve(application_id, operation_id, task, provenance)

    def activate(self, command: DraftCommand, prepared: PreparedDraft) -> DraftResult:
        with self.transactions.write() as tx:
            result = self.activation.activate_generation(tx, command, prepared)
        self.store_working_draft(prepared.source)
        return result

    def activate_regeneration(self, prepared: PreparedRegeneration) -> RegenerationResult:
        with self.transactions.write() as tx:
            result = self.activation.activate_regeneration(tx, prepared)
        self.store_working_draft(prepared.source)
        return result

    def apply_selection_change(self, command, *, analysis_service):
        return self.selection_changes.apply(command, analysis_service=analysis_service)

    _lineage = staticmethod(validation_lineage)
    _compose = staticmethod(compose)
    _require_content_hash = staticmethod(require_content_hash)

    def draft(self, command: DraftCommand) -> DraftResult:
        """Build the working draft from one exact analysis.

        The analysis is named by the caller for the same reason the snapshot is
        in `analyze`: a command that resolves `latest` itself can draft from an
        analysis the caller never saw.
        """
        self.load_active_application(command.application_id)
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
        profiles, policies = (knowledge.profiles, knowledge.policies)
        analysis_id = command.job_analysis_id
        try:
            record = self.analysis_record(analysis_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job analysis: {analysis_id}") from exc
        try:
            plan = self.selection_plan(command.selection_plan_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown selection plan: {command.selection_plan_id}") from exc
        mismatch = draft_source_mismatch(command.application_id, analysis_id, record, plan)
        if mismatch == "analysis":
            raise LineageBroken(
                f"analysis {analysis_id} does not belong to application {command.application_id}"
            )
        if mismatch == "selection_plan":
            raise LineageBroken(
                f"selection plan {plan.id} does not belong to application {command.application_id} and analysis {analysis_id}"
            )
        if command.parent_revision_id is not None:
            try:
                parent = self.approved_revision(command.parent_revision_id)
            except UnknownRecord as exc:
                raise UnknownRecord(
                    f"unknown parent approved revision: {command.parent_revision_id}"
                ) from exc
            if parent.application_id != command.application_id:
                raise LineageBroken(
                    f"approved revision {parent.id} does not belong to application {command.application_id}"
                )
        if plan.profile_version != profiles.version:
            raise StateConflict(
                f"selection plan {plan.id} froze profile version {plan.profile_version}, but knowledge now reports {profiles.version}; analyze again to obtain a plan for the current Profile"
            )
        if plan.selection_policy_version != policies.version:
            raise StateConflict(
                f"selection plan {plan.id} froze selection policy version {plan.selection_policy_version}, but knowledge now reports {policies.version}; analyze again to obtain a plan for the current selection policy"
            )
        analysis = record["analysis"]
        try:
            latest_snapshot = self.latest_snapshot(command.application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        if record["job_snapshot_id"] != latest_snapshot["id"]:
            raise StateConflict(
                f"job snapshot {latest_snapshot['id']} is newer than the analysis in hand; analyze the new snapshot before drafting against it"
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
        review_evidence: ProviderEvidence | None = None
        if command.provider == "openai":
            if operation_id is None:
                raise PreconditionFailed(
                    "AI generation runs as an Operation; there is no synchronous form"
                )
            draft, evidence, review_evidence = self._propose_wording(
                command.application_id,
                operation_id,
                draft,
                analysis,
                knowledge,
                model=command.model,
                reasoning_effort=command.reasoning_effort,
            )
        return PreparedDraft(
            source=draft,
            analysis=analysis,
            plan_id=plan.id,
            knowledge=knowledge,
            evidence=evidence,
            review_evidence=review_evidence,
        )

    def _propose_wording(
        self,
        application_id: str,
        operation_id: str,
        draft: DraftDocument,
        analysis: JobAnalysis,
        knowledge: Knowledge,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> tuple[DraftDocument, ProviderEvidence, ProviderEvidence | None]:
        """`draft_resume`: ask for wording over a document the engine composed.

        The provider never decides *which* facts appear - the SelectionPlan
        already did, and the document handed to it is the plan's own. It
        proposes how the selected facts are worded, and every line comes back
        through `apply_claim_edit`. Wording its own facts do not support is
        refused as `ProposalRejected`, not saved as a pending claim: §14's
        pending rule is for a person mid-edit, not for a wrong answer.
        """
        selected = sorted(
            {
                fact_id
                for section in draft.sections
                for claim in section.claims
                for fact_id in claim.fact_ids
            }
        )
        snapshot = self.snapshot_source(draft.job_snapshot_id)
        job_text = ""
        if self.snapshot_payloads is not None and snapshot.get("payload_path"):
            try:
                job_text = self.snapshot_payloads.read_snapshot(
                    snapshot["payload_path"], snapshot["source_hash"]
                )
            except (OSError, ValueError) as exc:
                raise InfrastructureFailure(f"could not read job snapshot payload: {exc}") from exc
        answered = self.provider.draft_resume(
            DraftResumeContext(
                job_analysis={
                    "track": analysis.track.value,
                    "profile": analysis.profile.value,
                    "emphasis": draft.emphasis.value,
                    "language": analysis.language,
                    "keywords": list(analysis.keywords),
                },
                job_text=job_text,
                requirements=[item.model_dump(mode="json") for item in analysis.requirements],
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
            ),
            model=model,
            reasoning_effort=reasoning_effort,
        )
        evidence = self.preserve(application_id, operation_id, "draft_resume", answered.provenance)
        with evidence_attached(evidence):
            updated = apply_proposed_claims(
                draft,
                answered.proposal.claims,
                knowledge.facts,
                set(selected),
                task="draft_resume",
                allow_semantic_review=True,
            )
        updated, review_evidence = self._review_pending_claims(
            application_id,
            operation_id,
            updated,
            knowledge,
            selected,
            evidence,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        return (updated, evidence, review_evidence)

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
        self.load_active_application(application_id)
        knowledge = self.load_knowledge()
        facts, profiles, policies = (knowledge.facts, knowledge.profiles, knowledge.policies)
        working = self.active_working_draft(application_id)
        draft = working.source
        _, analysis = self.bound_analysis(application_id, draft, profiles, facts)
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
        self.store_working_draft(changed.source)
        report = run_draft_validation(
            changed.source,
            serialize_markdown(changed.source),
            facts,
            profiles.get(updated.profile),
            analysis,
            plan=self.selection_plan(changed.selection_plan_id),
            policies=policies,
            presentations=knowledge.presentations,
        )
        self.record_validation(
            application_id, "manual-claim-edit", report, lineage=self._lineage(changed, knowledge)
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
        self.load_active_application(working.application_id)
        self._require_content_hash(working, command.expected_content_hash)
        knowledge = self.load_knowledge()
        facts, profiles = (knowledge.facts, knowledge.profiles)
        self.bound_analysis(working.application_id, working.source, profiles, facts)
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
        for claim_id in command.claim_removals:
            try:
                patched = remove_claim(patched, claim_id, facts)
            except KeyError as exc:
                raise UnknownRecord(f"unknown claim in the working draft: {claim_id}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim removal rejected: {exc}") from exc
        added_claim_ids: set[str] = set()
        for addition in command.claim_additions:
            try:
                patched, new_claim_id = add_claim(patched, addition.section, addition.text, facts)
            except KeyError as exc:
                raise UnknownRecord(
                    f"unknown section in the working draft: {addition.section}"
                ) from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim addition rejected: {exc}") from exc
            added_claim_ids.add(new_claim_id)
        try:
            patched = reorder_draft(
                patched, section_order=command.section_order, claim_orders=command.claim_orders
            )
        except KeyError as exc:
            raise UnknownRecord(f"unknown section in the working draft: {exc.args[0]}") from exc
        except ValueError as exc:
            raise PreconditionFailed(f"draft reorder rejected: {exc}") from exc
        changed = self._commit_edit(working, patched)
        self.store_working_draft(changed.source)
        edited = {edit.claim_id for edit in command.claim_edits} | added_claim_ids
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
        self._require_content_hash(working, expected_content_hash)
        if working.job_analysis_id != job_analysis_id:
            raise LineageBroken(
                f"working draft {working.id} was built from analysis {working.job_analysis_id}, not {job_analysis_id}"
            )
        if working.selection_plan_id != selection_plan_id:
            raise LineageBroken(
                f"working draft {working.id} was built from selection plan {working.selection_plan_id}, not {selection_plan_id}"
            )
        knowledge = self.load_knowledge()
        record = self.analysis_record(working.job_analysis_id)
        return (working, knowledge, record["analysis"])

    def _review_pending_claims(
        self,
        application_id: str,
        operation_id: str,
        draft: DraftDocument,
        knowledge: Knowledge,
        selected: list[str],
        writer_evidence: ProviderEvidence,
        *,
        model: str | None,
        reasoning_effort: str | None,
    ) -> tuple[DraftDocument, ProviderEvidence | None]:
        pending_ids = {
            claim.claim_id for claim in draft_claims(draft) if claim.claim_type == "pending"
        }
        if not pending_ids:
            return draft, None
        claims = [
            {
                "claim_id": claim.claim_id,
                "section": section.name,
                "text": claim.text,
                "fact_ids": list(claim.fact_ids),
            }
            for section in draft.sections
            for claim in section.claims
            if claim.claim_id in pending_ids
        ]
        try:
            reviewed = self.provider.assess_claim_support(
                AssessClaimSupportContext(
                    language=draft.language,
                    claims=claims,
                    allowed_facts=fact_context(knowledge.facts, selected, draft.language),
                ),
                model=model,
                reasoning_effort=reasoning_effort,
            )
            evidence = self.preserve(
                application_id, operation_id, "assess_claim_support", reviewed.provenance
            )
            with evidence_attached(evidence):
                authorized = authorize_semantically_reviewed_claims(
                    draft, reviewed.proposal, knowledge.facts, evidence
                )
        except ApplicationError as exc:
            exc.completed_evidence = (writer_evidence,)
            raise
        return authorized, evidence

    def prepare_section_regeneration(
        self, command: RegenerateSectionCommand, *, operation_id: str
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
        section = next((item for item in draft.sections if item.name == command.section), None)
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
            ),
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_section", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.section != section.name:
                raise ProposalRejected(
                    f"regenerate_section answered for section {proposed.section!r}, not {section.name!r}"
                )
            updated = apply_proposed_claims(
                draft,
                proposed.claims,
                knowledge.facts,
                set(allowed),
                task="regenerate_section",
                allow_semantic_review=True,
            )
        updated, review_evidence = self._review_pending_claims(
            command.application_id,
            operation_id,
            updated,
            knowledge,
            allowed,
            evidence,
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        return PreparedRegeneration(
            working=working,
            source=updated,
            claim_ids=[str(claim.claim_id) for claim in proposed.claims],
            evidence=evidence,
            review_evidence=review_evidence,
        )

    def prepare_claim_regeneration(
        self, command: RegenerateClaimCommand, *, operation_id: str
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
            ),
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        evidence = self.preserve(
            command.application_id, operation_id, "regenerate_claim", answered.provenance
        )
        proposed = answered.proposal
        with evidence_attached(evidence):
            if proposed.claim_id != claim.claim_id:
                raise ProposalRejected(
                    f"regenerate_claim answered for claim {proposed.claim_id!r}, not {claim.claim_id!r}"
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
                allow_semantic_review=True,
            )
        updated, review_evidence = self._review_pending_claims(
            command.application_id,
            operation_id,
            updated,
            knowledge,
            allowed,
            evidence,
            model=command.model,
            reasoning_effort=command.reasoning_effort,
        )
        return PreparedRegeneration(
            working=working,
            source=updated,
            claim_ids=[proposed.claim_id],
            evidence=evidence,
            review_evidence=review_evidence,
        )

    @staticmethod
    def _analysis_context(analysis: JobAnalysis) -> dict:
        """The narrow analysis view a wording task needs.

        Requirements are relevant writing context; Fit and approval routing remain policy.
        """
        return {
            "track": analysis.track.value,
            "profile": analysis.profile.value,
            "emphasis": analysis.emphasis.value,
            "language": analysis.language,
            "keywords": list(analysis.keywords),
            "requirements": [item.model_dump(mode="json") for item in analysis.requirements],
        }
