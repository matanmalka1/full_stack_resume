"""Archiving a working-draft version as an immutable historical payload."""

from __future__ import annotations

import json
from typing import Any

from ....domain.drafts import seal_draft
from ....domain.models import AuditRecord, WorkingDraft
from ....util import new_id, utc_now
from ...commands import (
    ArchivedWorkingDraftResult,
    ArchiveWorkingDraftCommand,
    ReplaceWorkingDraftCommand,
)
from ...errors import (
    # Re-exported: the API and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    LineageBroken,
    StateConflict,
)
from ...ports import DraftRepository, SnapshotPayload
from .common import DraftServiceBase


class DraftArchival(DraftServiceBase):
    """§14: Keep, then clear - the snapshot is registered before the pointer moves."""

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

    def _kept_snapshot(self, working: WorkingDraft) -> dict[str, Any] | None:
        """The historical snapshot already registered *and still intact* for this version.

        Identity is the draft, its edit version, and its content hash together - the same
        trio the Operation freezes. Two of them would not be enough: an edit version is
        only unique within one draft, and a content hash can repeat across drafts.

        The registration alone is not the answer. A row says a snapshot was written once,
        not that its payload is still there or still says what it said, and treating the
        row as proof would let a replacement overwrite the active draft against a
        historical copy that has been moved, deleted, or altered - losing the wording the
        Keep decision existed to preserve. So the payload is verified, and only `ok`
        counts as a Keep already taken. Anything else is a refusal rather than a silent
        continue: this engine already distinguishes missing from tampered everywhere else
        it re-derives itself from stored evidence, and a replacement is exactly the moment
        that distinction is load-bearing.
        """
        for record in self.repo.artifact_versions(working.application_id):
            if record["artifact_type"] != "working_draft_snapshot":
                continue
            metadata = json.loads(record["metadata_json"] or "{}")
            if not (
                metadata.get("working_draft_id") == working.id
                and metadata.get("edit_version") == working.edit_version
                and metadata.get("content_hash") == working.content_hash
            ):
                continue
            state = self.revision_payloads.verify_payload(record["path"], record["content_hash"])
            if state == "ok":
                return record
            raise StateConflict(
                f"the historical snapshot of working draft {working.id} version "
                f"{working.edit_version} is {state}; the replacement is refused rather "
                "than run against a copy that cannot be trusted"
            )
        return None

    def prepare_replacement(self, command: ReplaceWorkingDraftCommand) -> WorkingDraft:
        """§14: take the Keep decision before anything is replaced.

        Replacement itself is the draft Operation, which commits the new
        document over the same active record in one write - so nothing is
        deleted before the replacement succeeds, and a failed Operation leaves
        the existing draft exactly as it was. What has to happen first is Keep:
        the historical snapshot is materialized here, and it stays true whether
        or not the replacement that follows it succeeds.

        Keep is an ensure, not a do. It sits between an idempotency receipt being
        claimed and the Operation being created, so a crash in that gap leaves a
        pending receipt with the snapshot already written - and re-materializing
        it would fail on the immutable path that now exists, sticking the command
        permanently for a step that had in fact succeeded. A snapshot already
        registered for this exact draft, version, and content hash is that
        success, and is recognized rather than repeated: the record is immutable,
        so an existing one cannot be a different answer to the same question.
        """
        working = self._working(command.working_draft_id, command.expected_edit_version)
        if working.application_id != command.application_id:
            raise LineageBroken(
                f"working draft {working.id} does not belong to application "
                f"{command.application_id}"
            )
        if not command.keep_previous:
            return working
        if self._kept_snapshot(working) is not None:
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
