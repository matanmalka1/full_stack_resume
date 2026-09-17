"""§15: approving exactly the content one named ValidationRun passed."""

from __future__ import annotations

from dataclasses import asdict

from ....domain.analysis.projection import fit_level
from ....domain.analysis.projection import gaps as project_gaps
from ....domain.contracts.drafts import (
    DraftDocument,
    WorkingDraft,
)
from ....domain.draft_markdown import serialize_markdown
from ....domain.drafts import seal_draft
from ....domain.knowledge import Knowledge
from ....util import canonical_json, new_id, sha256_text, utc_now
from ...chain import ChainError, check_loaded_draft_chain
from ...commands import ApprovalResult, ApproveDraftCommand
from ...errors import (
    IDEMPOTENCY_KEY_REUSED,
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    VALIDATION_STALE,
    WORKING_PROJECTION_DIVERGED,
    ApplicationError,
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ...ports import (
    ArtifactStore,
    KnowledgeStore,
    Renderer,
    RevisionPayloadStore,
    TransactionManager,
)
from ...ports.drafts import DraftApprovalContext, DraftApprovalSourceReader, DraftLifecycleStore
from ...ports.idempotency import IdempotencyStore
from ..analysis.service import load_analysis_knowledge
from .approval_commit import ApprovalCommitter, PreparedApproval
from .inputs import require_working_version


class DraftApprovalService:
    """The trust boundary: immutable payloads, then the records that name them."""

    def __init__(
        self,
        *,
        transactions: TransactionManager,
        drafts: DraftLifecycleStore,
        sources: DraftApprovalSourceReader,
        receipts: IdempotencyStore,
        knowledge: KnowledgeStore,
        artifacts: ArtifactStore,
        renderer: Renderer,
        payloads: RevisionPayloadStore,
        committer: ApprovalCommitter,
    ):
        self.transactions = transactions
        self.drafts = drafts
        self.sources = sources
        self.receipts = receipts
        self._knowledge = knowledge
        self.artifacts = artifacts
        self.renderer = renderer
        self.revision_payloads = payloads
        self.committer = committer

    def load_knowledge(self) -> Knowledge:
        return load_analysis_knowledge(self._knowledge)

    def candidate(self):
        return self.load_knowledge().candidate

    def working_markdown(self, application_id: str) -> str:
        try:
            return self.artifacts.working_markdown(application_id)
        except OSError as exc:
            raise InfrastructureFailure(f"could not read working Markdown: {exc}") from exc

    def _working(self, working_draft_id: str, expected_version: int) -> WorkingDraft:
        with self.transactions.read() as tx:
            try:
                working = self.drafts.working_draft(tx, working_draft_id)
            except UnknownRecord as exc:
                raise UnknownRecord(f"unknown working draft: {working_draft_id}") from exc
        require_working_version(working, expected_version)
        return working

    def _require_synced_projection(self, application_id: str, draft: DraftDocument) -> None:
        """Refuse to approve while the projection holds edits storage has not imported.

        The database is authoritative from boundary 2a, and approval rebuilds the
        projection from it, so an unimported file edit would be destroyed without
        a word. `validate` deliberately reports on the stored draft instead of
        refusing, because that report is true; approval is the trust boundary and
        the point of loss, so the refusal belongs here.

        The edit is never touched. Editing the projection file by hand is no
        longer a supported path - claims are edited through the draft's own
        autosave, which the database sees - so the way forward is to make the
        edit again there, or to regenerate and discard it. The refusal stays
        either way: silently destroying a user's writing is the failure this
        exists to prevent, and it does not become acceptable because the file
        was edited outside the product.
        """
        stored = self.working_markdown(application_id)
        if stored and stored != serialize_markdown(draft):
            raise StateConflict(
                "the working Markdown projection differs from the stored draft; "
                "re-apply the change through the draft editor, or regenerate the "
                "draft to discard it",
                code=WORKING_PROJECTION_DIVERGED,
            )

    def _require_binding_validation(
        self,
        working: WorkingDraft,
        validation_run_id: str,
        knowledge: Knowledge,
        context: DraftApprovalContext,
    ) -> None:
        """§15's four binding conditions, checked against a run approval did not create.

        This is the whole point of taking the run ID as an argument. While
        approval validated for itself, the four checks compared a run against
        the draft that had just produced it, so they could not fail and proved
        nothing. Against a run the user obtained earlier they are real: an edit
        after validation moves the version, a re-seal moves the hash, and a run
        from another draft names another draft.
        """
        lineage = context.validation_lineage
        report = context.validation_report
        if lineage is None or report is None:
            raise UnknownRecord(f"unknown validation run: {validation_run_id}")
        mismatched = [
            name
            for name, recorded, current in (
                ("working draft", lineage.working_draft_id, working.id),
                ("edit version", lineage.edit_version, working.edit_version),
                ("content hash", lineage.content_hash, working.content_hash),
                (
                    "knowledge context",
                    lineage.knowledge_context_hash,
                    knowledge.document_context_hash(),
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

    def _prepare_approval(
        self, command: ApproveDraftCommand, *, revision_id: str | None = None
    ) -> PreparedApproval:
        """§15: approve exactly the content one named ValidationRun passed.

        No validation runs here. Approval consumes evidence; it does not
        manufacture it.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        application_id = working.application_id
        with self.transactions.read() as tx:
            context = self.sources.approval_context(tx, working, command.validation_run_id)
        if context.deleted_at is not None:
            raise StateConflict(f"application is deleted: {application_id}")
        if context.quarantined_mutation_id is not None:
            raise PreconditionFailed(
                f"approval blocked by quarantined Knowledge mutation {context.quarantined_mutation_id}"
            )
        self._require_synced_projection(application_id, working.source)
        knowledge = self.load_knowledge()
        self._require_binding_validation(working, command.validation_run_id, knowledge, context)
        validation_id = command.validation_run_id
        facts, profiles = knowledge.facts, knowledge.profiles
        draft = working.source
        # The database is authoritative. Seal the exact stored document and commit its
        # immutable payloads before any revision row can become visible.
        sealed, markdown, structured_json = seal_draft(draft)
        if sealed.content_hash != working.content_hash:
            raise StateConflict("working draft content hash changed before approval")
        # The decision record explains the draft being approved, so it is bound to
        # that draft's own analysis. A newer analysis does not get to describe an
        # older document.
        chain = check_loaded_draft_chain(context.chain, application_id, draft, profiles, facts)
        try:
            analysis_id, analysis = chain.bound()
        except ChainError as exc:
            raise LineageBroken(f"draft chain rejected: {exc}") from exc
        selection_plan = context.plan
        if selection_plan is None:
            raise UnknownRecord(f"no selection plan {working.selection_plan_id}")
        decision_overrides = dict(analysis.user_override)
        if selection_plan.plan.emphasis_override is not None:
            decision_overrides["emphasis"] = selection_plan.plan.emphasis_override.value
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
        structured = {
            "company": context.company,
            "target_job": context.target_role,
            "track": draft.track.value,
            "profile": draft.profile.value,
            "emphasis": draft.emphasis.value,
            # The language of the exact document being approved, not of whatever
            # analysis is current: the record explains this draft, and a later
            # re-analysis under a language override must not restate its language.
            "language": draft.language,
            # Frozen here on purpose, unlike on the analysis. This record is what
            # the user approved against, and Fit and gaps as they stood at that
            # moment are part of that evidence: a later change to how they are
            # projected must not rewrite what an approved revision says it was
            # approved with. The analysis stores none of it; the record keeps
            # the one copy that is allowed to be a copy.
            "summary": analysis.summary,
            "fit": fit_level(analysis.requirements).value,
            "gaps": [asdict(gap) for gap in project_gaps(analysis.requirements, facts)],
            "selected_fact_ids": draft.selected_fact_ids,
            "omitted_facts": draft.omitted_facts,
            "derived_statements": [
                claim.model_dump(mode="json")
                for section in draft.sections
                for claim in section.claims
                if claim.claim_type in {"composite", "derived"}
            ],
            "user_overrides": decision_overrides,
            "fact_store_version": facts.version,
            "job_snapshot_id": draft.job_snapshot_id,
            "job_analysis_id": analysis_id,
            "artifact_paths": {
                "markdown": published.markdown.reference,
            },
            "recruiter_pdf_filename": recruiter_pdf_filename,
        }
        decision_summary = (
            f"Approved {draft.profile.value} / {draft.emphasis.value} CV for {context.company}."
        )
        return PreparedApproval(
            application_id,
            revision_id,
            working.id,
            validation_id,
            draft.job_snapshot_id,
            analysis_id,
            published.structured.reference,
            published.structured.sha256,
            published.markdown.reference,
            published.markdown.sha256,
            draft.track.value,
            draft.profile.value,
            draft.emphasis.value,
            facts.version,
            new_id(),
            canonical_json(structured),
            decision_summary,
            new_id(),
            command.actor_type,
            command.client,
            now,
        )

    def _approve(
        self,
        command: ApproveDraftCommand,
        revision_id: str | None,
        receipt_id: str | None,
    ) -> ApprovalResult:
        prepared = self._prepare_approval(command, revision_id=revision_id)
        with self.transactions.write() as tx:
            self.drafts.lock_application(tx, prepared.application_id)
            return self.committer.commit(tx, prepared, receipt_id)

    def approve_draft(
        self, command: ApproveDraftCommand, *, revision_id: str | None = None
    ) -> ApprovalResult:
        return self._approve(command, revision_id, None)

    def _approval_payload(self, command: ApproveDraftCommand) -> dict[str, object]:
        with self.transactions.read() as tx:
            try:
                working = self.drafts.working_draft(tx, command.working_draft_id)
            except UnknownRecord as exc:
                raise UnknownRecord(f"unknown working draft: {command.working_draft_id}") from exc
        return {**command.model_dump(mode="json"), "content_hash": working.content_hash}

    def approve_idempotent(
        self, command: ApproveDraftCommand, *, idempotency_key: str
    ) -> ApprovalResult:
        with self.transactions.read() as tx:
            existing = self.receipts.idempotency_receipt(tx, "approve_draft", idempotency_key)
        if existing is not None:
            if existing["payload"].get("working_draft_id") != command.working_draft_id:
                raise StateConflict(
                    "idempotency key already used for another working draft",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            payload = self._approval_payload(command)
            recorded_payload = dict(existing["payload"])
            with self.transactions.read() as tx:
                replay = self.sources.approval_replay(tx, existing["reserved_entity_id"])
            if replay.provenance is not None:
                for name in ("actor_type", "client"):
                    if name not in recorded_payload and name in replay.provenance:
                        recorded_payload[name] = replay.provenance[name]
            if recorded_payload != payload:
                raise StateConflict(
                    "idempotency key already used with a different approval payload",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            if replay.result is not None:
                if existing["status"] == "pending":
                    with self.transactions.write() as tx:
                        self.receipts.complete_idempotency_receipt(
                            tx, existing["id"], replay.result.model_dump(mode="json")
                        )
                return replay.result
            receipt = existing
        else:
            payload = self._approval_payload(command)
            with self.transactions.write() as tx:
                receipt = self.receipts.claim_idempotency_receipt(
                    tx, "approve_draft", idempotency_key, payload, reserved_entity_id=new_id()
                )
        try:
            return self._approve(command, receipt["reserved_entity_id"], receipt["id"])
        except ApplicationError:
            with self.transactions.read() as tx:
                recovered = self.sources.approval_replay(tx, receipt["reserved_entity_id"]).result
            if recovered is None:
                raise
            with self.transactions.write() as tx:
                self.receipts.complete_idempotency_receipt(
                    tx, receipt["id"], recovered.model_dump(mode="json")
                )
            return recovered
