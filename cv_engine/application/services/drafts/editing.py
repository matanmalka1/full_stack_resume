"""Manual editing: one claim, an imported Markdown projection, or an autosave patch."""

from __future__ import annotations

from ....domain.drafts import apply_claim_edit, draft_claims, remove_claim
from ....domain.validation import validate_draft as run_draft_validation
from ...commands import EditResult, UpdateWorkingDraftCommand, WorkingDraftUpdateResult
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    PreconditionFailed,
    StateConflict,
    UnknownRecord,
)
from ..base import bound_analysis, working_draft_record
from .common import DraftServiceBase


class DraftEditing(DraftServiceBase):
    """§14: the edits a person makes to a draft they are already holding."""

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
            plan=self.repo.selection_plan(changed.selection_plan_id),
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
        # After the edits, so a patch that rewrites one claim and removes
        # another is applied in the order the user meant: the removal decides
        # about a line as it stands after this patch, not before it.
        for claim_id in command.claim_removals:
            try:
                patched = remove_claim(patched, claim_id, facts)
            except KeyError as exc:
                raise UnknownRecord(f"unknown claim in the working draft: {claim_id}") from exc
            except ValueError as exc:
                raise PreconditionFailed(f"claim removal rejected: {exc}") from exc
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
