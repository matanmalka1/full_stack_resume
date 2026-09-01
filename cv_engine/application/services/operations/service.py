"""Submission, cancellation, retry, and query for durable Operations.

What a submitted Operation *does* lives in `handlers`; this module owns the
record: the frozen sources, the idempotency key, and the `OperationView` every
method narrows to before returning.
"""

from __future__ import annotations

from typing import cast

from ....util import canonical_json, new_id, sha256_text
from ...commands import (
    AnalyzeCommand,
    ApprovalResult,
    ApproveDraftCommand,
    DraftCommand,
    ProposeSelectionPlanCommand,
    RegenerateClaimCommand,
    RegenerateSectionCommand,
    RenderCommand,
    ReplaceWorkingDraftCommand,
)
from ...errors import (
    IDEMPOTENCY_KEY_REUSED,
    ApplicationError,
    LineageBroken,
    StateConflict,
    UnknownRecord,
)
from ...operations import (
    CreateOperation,
    OperationSources,
    OperationType,
    OperationView,
    as_operation_view,
    is_terminal_operation,
)
from ...ports import (
    DraftRepository,
    OperationRepository,
    PreparationRepository,
    ReadinessRepository,
)
from ..analysis import AnalysisService
from ..base import ServiceBase
from ..drafts import DraftService
from ..rendering import RenderingService
from .common import _model_hash, analysis_knowledge_context_hash


class OperationService(ServiceBase[OperationRepository]):
    """Create, cancel, retry, and query durable Operations.

    Every method returns `OperationView`, never the runner record. Submission is
    included: a `202` body is the same representation `GET /operations/{id}`
    returns, so a submit that handed back `PersistedOperation` would put the
    payload, the frozen sources, the lease, and the idempotency key into an
    acceptance response. The narrowing is here rather than in each caller,
    because a caller that forgets is exactly how it leaked before.
    """

    def submit_analysis(
        self,
        command: AnalyzeCommand,
        *,
        idempotency_key: str,
        analysis_service: AnalysisService,
    ) -> OperationView:
        preparation = cast(PreparationRepository, self.repo)
        try:
            snapshot = preparation.get_snapshot(command.job_snapshot_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job snapshot: {command.job_snapshot_id}") from exc
        if snapshot["application_id"] != command.application_id:
            raise LineageBroken(
                f"job snapshot {command.job_snapshot_id} does not belong to application "
                f"{command.application_id}"
            )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.ANALYZE_JOB,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=command.job_snapshot_id,
                job_snapshot_hash=snapshot["source_hash"],
                knowledge_context_hash=analysis_knowledge_context_hash(analysis_service),
            ),
            provider=command.provider,
            model=command.model,
        )
        return as_operation_view(self.repo.create_operation(request))

    def submit_draft(
        self,
        command: DraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
        operation_id: str | None = None,
    ) -> OperationView:
        drafts = cast(DraftRepository, self.repo)
        try:
            analysis = drafts.get_analysis(command.job_analysis_id)
            plan = drafts.selection_plan(command.selection_plan_id)
            snapshot = drafts.get_snapshot(analysis["job_snapshot_id"])
        except UnknownRecord as exc:
            raise UnknownRecord("unknown source for draft generation") from exc
        if (
            analysis["application_id"] != command.application_id
            or plan.application_id != command.application_id
            or plan.job_analysis_id != command.job_analysis_id
        ):
            raise LineageBroken("draft sources do not belong to the named Application")
        if command.parent_revision_id is not None:
            readiness = cast(ReadinessRepository, self.repo)
            try:
                parent = readiness.approved_revision(command.parent_revision_id)
            except UnknownRecord as exc:
                raise UnknownRecord(
                    f"unknown parent approved revision: {command.parent_revision_id}"
                ) from exc
            if parent.application_id != command.application_id:
                raise LineageBroken(
                    f"approved revision {parent.id} does not belong to application "
                    f"{command.application_id}"
                )
        knowledge_hash = sha256_text(canonical_json(draft_service.load_knowledge().versions()))
        # §14: a replacement freezes the identity of the draft it is replacing, so the
        # runner can re-check at activation that the record is still the one the user
        # meant. Generation with nothing to replace freezes none, and the validator on
        # `OperationSources` requires the three fields together or not at all.
        replaced_id: str | None = None
        replaced_version: int | None = None
        replaced_hash: str | None = None
        if command.replaces_working_draft_id is not None:
            existing = drafts.working_draft(command.replaces_working_draft_id)
            if existing.application_id != command.application_id:
                raise LineageBroken(
                    f"working draft {existing.id} does not belong to application "
                    f"{command.application_id}"
                )
            if existing.edit_version != command.replaces_expected_edit_version:
                raise StateConflict(
                    f"working draft {existing.id} is at edit version "
                    f"{existing.edit_version}, not {command.replaces_expected_edit_version}"
                )
            replaced_id = existing.id
            replaced_version = existing.edit_version
            replaced_hash = existing.content_hash
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.CREATE_DRAFT,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=snapshot["id"],
                job_snapshot_hash=snapshot["source_hash"],
                job_analysis_id=command.job_analysis_id,
                selection_plan_id=command.selection_plan_id,
                knowledge_context_hash=knowledge_hash,
                working_draft_id=replaced_id,
                working_draft_edit_version=replaced_version,
                working_draft_content_hash=replaced_hash,
                dependency_hashes={
                    "job_analysis": _model_hash(analysis["analysis"]),
                    "selection_plan": _model_hash(plan),
                },
            ),
            # The mode the client chose, recorded on the Operation. It also
            # decides whether the AI resource slot is required, which
            # `required_operation_resources` derives from these two fields
            # rather than from a second list of AI operation types.
            provider=command.provider,
            model="rules-v1" if command.provider == "deterministic" else None,
        )
        return as_operation_view(self.repo.create_operation(request, operation_id=operation_id))

    def submit_selection_plan_proposal(
        self,
        command: ProposeSelectionPlanCommand,
        *,
        idempotency_key: str,
        analysis_service: AnalysisService,
    ) -> OperationView:
        """§13, AI mode: queue the proposal; no provider call in a request.

        The analysis is frozen with its content hash, so a review decision that
        replaces the analysis while this is queued fails the source check
        instead of proposing a plan for an analysis nobody is looking at.
        """
        preparation = cast(PreparationRepository, self.repo)
        try:
            analysis = preparation.get_analysis(command.job_analysis_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown job analysis: {command.job_analysis_id}") from exc
        if analysis["application_id"] != command.application_id:
            raise LineageBroken(
                f"job analysis {command.job_analysis_id} does not belong to application "
                f"{command.application_id}"
            )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.PROPOSE_SELECTION_PLAN,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=analysis["job_snapshot_id"],
                job_analysis_id=command.job_analysis_id,
                knowledge_context_hash=analysis_knowledge_context_hash(analysis_service),
                dependency_hashes={"job_analysis": _model_hash(analysis["analysis"])},
            ),
            provider="openai",
            model=command.model,
        )
        return as_operation_view(self.repo.create_operation(request))

    def submit_regeneration(
        self,
        command: RegenerateSectionCommand | RegenerateClaimCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> OperationView:
        """§14: queue one section or claim regeneration against an exact draft.

        The draft's three-part identity goes into the frozen sources, which is
        what the handler's `check_sources` re-checks at activation. The command
        also states the analysis and plan explicitly - `latest` never appears -
        so a regeneration cannot be launched against sources the client did not
        name.
        """
        drafts = cast(DraftRepository, self.repo)
        try:
            working = drafts.working_draft(command.working_draft_id)
            analysis = drafts.get_analysis(command.job_analysis_id)
            plan = drafts.selection_plan(command.selection_plan_id)
        except UnknownRecord as exc:
            raise UnknownRecord("unknown source for regeneration") from exc
        if (
            working.application_id != command.application_id
            or analysis["application_id"] != command.application_id
            or plan.application_id != command.application_id
            or plan.job_analysis_id != command.job_analysis_id
        ):
            raise LineageBroken("regeneration sources do not belong to the named Application")
        if working.edit_version != command.expected_edit_version:
            raise StateConflict(
                f"working draft {working.id} is at edit version {working.edit_version}, "
                f"not {command.expected_edit_version}"
            )
        if working.content_hash != command.expected_content_hash:
            raise StateConflict(
                f"working draft {working.id} has content hash {working.content_hash}, "
                f"not {command.expected_content_hash}"
            )
        operation_type = (
            OperationType.REGENERATE_SECTION
            if isinstance(command, RegenerateSectionCommand)
            else OperationType.REGENERATE_CLAIM
        )
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=operation_type,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_analysis_id=command.job_analysis_id,
                selection_plan_id=command.selection_plan_id,
                working_draft_id=working.id,
                working_draft_edit_version=working.edit_version,
                working_draft_content_hash=working.content_hash,
                knowledge_context_hash=sha256_text(
                    canonical_json(draft_service.load_knowledge().versions())
                ),
                dependency_hashes={
                    "job_analysis": _model_hash(analysis["analysis"]),
                    "selection_plan": _model_hash(plan),
                },
            ),
            provider="openai",
            model=None,
        )
        return as_operation_view(self.repo.create_operation(request))

    def submit_replacement_draft(
        self,
        command: ReplaceWorkingDraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> OperationView:
        """§14 replace: the Keep decision, then the same draft Operation.

        Replacement is generation against an Application that already has an
        active draft, so it queues the same `CREATE_DRAFT` work and inherits its
        frozen sources and `SOURCE_CHANGED` protection rather than growing a
        second path that would have to repeat them. What replacement adds is the
        two things generation has no opinion about: which exact draft version
        the user meant to replace, and whether to keep it.

        `prepare_replacement` is what proves the named draft belongs to the
        named Application before any of that starts.

        Order matters here, and it used to be wrong. Keep is a side effect that
        writes an immutable snapshot and an audit record, and it ran before the
        Operation existed - so a resent request with the same key materialized a
        second snapshot before reaching the idempotency check that would have
        recognized it as a replay. The replay is settled first now, against the
        payload the replacement would create; only a genuinely new command
        reaches Keep.

        The draft identity travels in the payload rather than being consumed
        here, which is also what makes two replacements distinguishable: the
        idempotency check hashes the payload, and a payload that named neither
        the draft nor its version made a replacement of version 8 look like a
        replay of the one sent for version 7.
        """
        draft_command = DraftCommand(
            application_id=command.application_id,
            job_analysis_id=command.job_analysis_id,
            selection_plan_id=command.selection_plan_id,
            provider=command.provider,
            replaces_working_draft_id=command.working_draft_id,
            replaces_expected_edit_version=command.expected_edit_version,
            replaces_keep_previous=command.keep_previous,
        )
        # The Operation is created first, and Keep runs only if this call is what created
        # it. `create_operation` settles the idempotency question atomically: it hands back
        # the existing Operation when the key and payload match, and raises
        # `IDEMPOTENCY_KEY_REUSED` when the key is reused with a different payload. The id
        # is generated here so that answer is legible - a replay comes back wearing an id
        # this call did not mint.
        intended_id = new_id()
        queued = self.submit_draft(
            draft_command,
            idempotency_key=idempotency_key,
            draft_service=draft_service,
            operation_id=intended_id,
        )
        if queued.id != intended_id:
            return queued
        draft_service.prepare_replacement(command)
        return queued

    def submit_render(
        self,
        command: RenderCommand,
        *,
        idempotency_key: str,
        rendering_service: RenderingService,
    ) -> OperationView:
        readiness = cast(ReadinessRepository, self.repo)
        try:
            revision = readiness.approved_revision(command.approved_revision_id)
            manifest = readiness.artifact_version_for_revision(
                command.approved_revision_id, "claim_manifest", "approved"
            )
            snapshot = readiness.get_snapshot(revision.job_snapshot_id)
        except UnknownRecord as exc:
            raise UnknownRecord(
                f"unknown approved revision: {command.approved_revision_id}"
            ) from exc
        if revision.application_id != command.application_id:
            raise LineageBroken("approved revision does not belong to the named Application")
        request = CreateOperation(
            application_id=command.application_id,
            operation_type=OperationType.RENDER_REVISION,
            payload=command.model_dump(mode="json"),
            idempotency_key=idempotency_key,
            sources=OperationSources(
                job_snapshot_id=revision.job_snapshot_id,
                job_snapshot_hash=snapshot["source_hash"],
                job_analysis_id=revision.job_analysis_id,
                selection_plan_id=revision.selection_plan_id,
                approved_revision_id=revision.id,
                knowledge_context_hash=sha256_text(
                    canonical_json(rendering_service.load_knowledge().versions())
                ),
                dependency_hashes={
                    "approved_revision": _model_hash(revision),
                    "claim_manifest": manifest["content_hash"],
                },
            ),
            provider="deterministic",
            model="playwright",
        )
        return as_operation_view(self.repo.create_operation(request))

    def cancel(self, operation_id: str) -> OperationView:
        """Cancel queued work outright; ask running work to stop (§19).

        The narrow view is the contract for every client of this service - the
        every caller alike. Only the runner reads the full record, and it
        reads it from the repository rather than from here.
        """
        return as_operation_view(self.repo.request_operation_cancellation(operation_id))

    def _approval_result(self, revision_id: str) -> ApprovalResult | None:
        drafts = cast(DraftRepository, self.repo)
        try:
            revision = drafts.approved_revision(revision_id)
            markdown = drafts.artifact_version_for_revision(
                revision_id, "resume_markdown", "approved"
            )
            manifest = drafts.artifact_version_for_revision(
                revision_id, "claim_manifest", "approved"
            )
            decision = drafts.decision_for_revision(revision_id)
        except UnknownRecord:
            return None
        return ApprovalResult(
            application_id=revision.application_id,
            revision_id=revision.id,
            version=revision.version_number,
            markdown_artifact_version_id=markdown["id"],
            manifest_artifact_version_id=manifest["id"],
            decision_record_id=decision["id"],
        )

    def _approval_payload(self, command: ApproveDraftCommand) -> dict[str, object]:
        """What the idempotency key is a key *for* (§15).

        All three command arguments plus the draft's content hash. The hash is
        not derivable from the other three - it is what the draft actually says
        right now - so without it a key replayed after an edit would look like
        the same request and return a revision of different content.
        """
        drafts = cast(DraftRepository, self.repo)
        try:
            working = drafts.working_draft(command.working_draft_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown working draft: {command.working_draft_id}") from exc
        return {
            "working_draft_id": command.working_draft_id,
            "expected_edit_version": command.expected_edit_version,
            "validation_run_id": command.validation_run_id,
            "content_hash": working.content_hash,
        }

    def approve_idempotent(
        self,
        command: ApproveDraftCommand,
        *,
        idempotency_key: str,
        draft_service: DraftService,
    ) -> ApprovalResult:
        command_type = "approve_draft"
        existing = self.repo.idempotency_receipt(
            command_type,
            idempotency_key,
        )
        if existing is not None:
            if existing["payload"].get("working_draft_id") != command.working_draft_id:
                raise StateConflict(
                    "idempotency key already used for another working draft",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            completed = self._approval_result(existing["reserved_entity_id"])
            if completed is not None:
                if existing["status"] == "pending":
                    self.repo.complete_idempotency_receipt(
                        existing["id"], completed.model_dump(mode="json")
                    )
                return completed
            if existing["payload"] != self._approval_payload(command):
                raise StateConflict(
                    "idempotency key already used for a different draft version",
                    code=IDEMPOTENCY_KEY_REUSED,
                )
            receipt = existing
        else:
            receipt = self.repo.claim_idempotency_receipt(
                command_type,
                idempotency_key,
                self._approval_payload(command),
                reserved_entity_id=new_id(),
            )
        try:
            result = draft_service.approve_draft(
                command,
                revision_id=receipt["reserved_entity_id"],
            )
        except ApplicationError:
            recovered = self._approval_result(receipt["reserved_entity_id"])
            if recovered is None:
                raise
            result = recovered
        self.repo.complete_idempotency_receipt(receipt["id"], result.model_dump(mode="json"))
        return result

    def retry(self, operation_id: str, *, idempotency_key: str) -> OperationView:
        """Queue a new Operation carrying `retry_of_operation_id` (§19).

        The original stays immutable, and reusing its idempotency key returns
        the original rather than creating a second attempt.
        """
        original = self.repo.operation(operation_id)
        if not is_terminal_operation(original.status):
            raise StateConflict("only a terminal Operation can be retried")
        request = CreateOperation(
            application_id=original.application_id,
            operation_type=original.operation_type,
            payload=original.payload,
            idempotency_key=idempotency_key,
            sources=original.sources,
            provider=original.provider,
            model=original.model,
            retry_of_operation_id=original.id,
        )
        return as_operation_view(self.repo.create_operation(request))

    def get(self, operation_id: str) -> OperationView:
        """Operation status as a query contract (§20), never the runner record."""
        return as_operation_view(self.repo.operation(operation_id))
