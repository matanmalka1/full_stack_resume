"""§15: approving exactly the content one named ValidationRun passed."""

from __future__ import annotations

from ....domain.draft_markdown import serialize_markdown
from ....domain.drafts import seal_draft
from ....domain.knowledge import Knowledge
from ....domain.models import AuditRecord, DecisionRecord, DraftDocument, WorkingDraft
from ....util import canonical_json, new_id, sha256_text, utc_now
from ...commands import ApprovalResult, ApproveDraftCommand
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    VALIDATION_STALE,
    WORKING_PROJECTION_DIVERGED,
    InfrastructureFailure,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ..base import bound_analysis
from .common import DraftServiceBase


class DraftApproval(DraftServiceBase):
    """The trust boundary: immutable payloads, then the records that name them."""

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
        # The database is authoritative. Seal the exact stored document and commit its
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
            # The language of the exact document being approved, not of whatever
            # analysis is current: the record explains this draft, and a later
            # re-analysis under a language override must not restate its language.
            "language": draft.language,
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
