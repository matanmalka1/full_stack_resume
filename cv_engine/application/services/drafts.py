from __future__ import annotations

import uuid

from ... import __version__
from ...domain.analysis.approval import unresolved_approval_reasons
from ...domain.draft_markdown import serialize_markdown, synchronize_markdown_claims
from ...domain.drafts import apply_claim_edit, build_draft, seal_draft
from ...domain.knowledge import Knowledge
from ...domain.models import (
    ApplicationStatus,
    DraftDocument,
    ValidationReport,
    ValidationRunLineage,
    WorkingDraft,
)
from ...domain.validation import validate_draft
from ...util import canonical_json, sha256_text, utc_now
from ..commands import (
    ApprovalResult,
    DraftCommand,
    DraftResult,
    EditResult,
)
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    LineageBroken,
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
    ValidationBlocked,
)
from ..ports import (
    DraftRepository,
)
from .base import ServiceBase


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

    def _commit_edit(self, working: WorkingDraft, source: DraftDocument) -> WorkingDraft:
        try:
            changed = self.repo.update_working_draft(
                working.id,
                working.edit_version,
                source,
            )
        except ValueError as exc:
            raise StateConflict(str(exc)) from exc
        return changed

    def draft(self, command: DraftCommand) -> DraftResult:
        """Build the working draft from one exact analysis.

        The analysis is named by the caller for the same reason the snapshot is
        in `analyze`: a command that resolves `latest` itself can draft from an
        analysis the caller never saw.
        """
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        analysis_id = command.job_analysis_id
        try:
            record = self.repo.get_analysis(analysis_id)
        except KeyError as exc:
            raise UnknownRecord(f"unknown job analysis: {analysis_id}") from exc
        if record["application_id"] != command.application_id:
            raise LineageBroken(
                f"analysis {analysis_id} does not belong to application {command.application_id}"
            )
        try:
            plan = self.repo.selection_plan(command.selection_plan_id)
        except KeyError as exc:
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
        except KeyError as exc:
            raise UnknownRecord(f"unknown application: {command.application_id}") from exc
        if record["job_snapshot_id"] != latest_snapshot["id"]:
            raise StateConflict(
                f"job snapshot {latest_snapshot['id']} is newer than the analysis in hand; "
                "analyze the new snapshot before drafting against it"
            )
        profile = profiles.get(analysis.profile)
        presentation_rules = knowledge.presentations
        try:
            draft = build_draft(
                application_id=command.application_id,
                job_snapshot_id=record["job_snapshot_id"],
                job_analysis_id=analysis_id,
                analysis=analysis,
                profile=profile,
                facts=facts,
                policies=policies,
                candidate=knowledge.candidate,
                presentations=presentation_rules,
                selection=plan.plan,
            )
        except ValueError as exc:
            raise PreconditionFailed(f"draft could not be built: {exc}") from exc
        working = self.repo.replace_active_working_draft(
            command.application_id,
            analysis_id,
            plan.id,
            draft,
        )
        stored = self.store_working_draft(working.source)
        report = validate_draft(
            working.source,
            stored.markdown,
            facts,
            profile,
            analysis,
            policies=policies,
            presentations=presentation_rules,
        )
        self.repo.record_validation(
            command.application_id,
            "pre-render",
            report,
            lineage=self._lineage(working, knowledge),
        )
        self.repo.record_generation_run(
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
                "ai_provider": "deterministic",
                "ai_model": "rules-v1",
                "task_contract_version": "1.0.0",
                "prompt_version": "system-v1",
                "job_analysis_version": analysis.analysis_version,
                "instruction_overrides": analysis.user_override,
                "status": "completed" if report.passed else "validation-failed",
            }
        )
        return DraftResult(
            application_id=command.application_id,
            job_analysis_id=analysis_id,
            selection_plan_id=plan.id,
            working_draft_id=working.id,
            edit_version=working.edit_version,
            validation=report,
        )

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

    def _validate_working(self, application_id: str) -> tuple[ValidationReport, str]:
        knowledge = self.load_knowledge()
        facts, profiles, policies = knowledge.facts, knowledge.profiles, knowledge.policies
        working = self.working_draft_record(application_id)
        draft = working.source
        _, analysis = self._bound_analysis(application_id, draft, profiles, facts)
        markdown = serialize_markdown(draft)
        report = validate_draft(
            draft,
            markdown,
            facts,
            profiles.get(draft.profile),
            analysis,
            policies=policies,
            presentations=knowledge.presentations,
        )
        validation_id = self.repo.record_validation(
            application_id,
            "pre-render",
            report,
            lineage=self._lineage(working, knowledge),
        )
        return report, validation_id

    def validate_working(self, application_id: str) -> ValidationReport:
        report, _validation_id = self._validate_working(application_id)
        return report

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
        working = self.working_draft_record(application_id)
        draft = working.source
        _, analysis = self._bound_analysis(application_id, draft, profiles, facts)
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
        report = validate_draft(
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
        working = self.working_draft_record(application_id)
        draft = working.source
        _, analysis = self._bound_analysis(application_id, draft, profiles, facts)
        try:
            updated = synchronize_markdown_claims(
                draft, self.working_markdown(application_id), facts
            )
        except ValueError as exc:
            raise PreconditionFailed(f"working draft synchronization rejected: {exc}") from exc
        changed = self._commit_edit(working, updated)
        stored = self.store_working_draft(changed.source)
        report = validate_draft(
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

    def approve(self, application_id: str) -> ApprovalResult:
        self._require_synced_projection(
            application_id, self.working_draft_record(application_id).source
        )
        report, validation_id = self._validate_working(application_id)
        if not report.passed:
            raise ValidationBlocked("approval blocked by pre-render validation", report)
        facts, profiles, _ = self.knowledge()
        working = self.working_draft_record(application_id)
        draft = working.source
        # SQLite is authoritative. Seal the exact stored document and commit its
        # immutable payloads before any revision row can become visible.
        sealed, markdown, structured_json = seal_draft(draft)
        if sealed.content_hash != working.content_hash:
            raise StateConflict("working draft content hash changed before approval")
        # The decision record explains the draft being approved, so it is bound to
        # that draft's own analysis. A newer analysis does not get to describe an
        # older document.
        analysis_id, analysis = self._bound_analysis(application_id, draft, profiles, facts)
        revision_id = str(uuid.uuid4())
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
            profiles.get(draft.profile).normalized_role, self.candidate(facts)
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
            "actor_type": "user",
            "client": "cli",
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
            decision_id = transaction.record_decision(
                application_id,
                markdown_version_id,
                draft.job_snapshot_id,
                analysis_id,
                structured,
                decision_summary,
            )
            transaction.record_event(
                application_id,
                "draft_approved",
                {
                    "approved_revision_id": revision.id,
                    "decision_record_id": decision_id,
                    "version": revision.version_number,
                },
            )
            if application["current_status"] == ApplicationStatus.READY.value:
                transaction.transition_status(
                    application_id,
                    ApplicationStatus.PREPARING,
                    "new approved version requires fresh rendering and ready validation",
                )
            uow.commit()
        return ApprovalResult(
            application_id=application_id,
            revision_id=revision.id,
            version=revision.version_number,
            markdown_artifact_version_id=markdown_version_id,
            manifest_artifact_version_id=manifest_version_id,
            decision_record_id=decision_id,
        )
