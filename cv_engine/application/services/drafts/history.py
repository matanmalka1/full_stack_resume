from __future__ import annotations

import json
from typing import Any

from ....domain.contracts.drafts import WorkingDraft
from ....domain.contracts.records import AuditRecord
from ....domain.drafts import seal_draft
from ....util import new_id, sha256_text, utc_now
from ...commands import (
    ArchivedWorkingDraftResult,
    ArchiveWorkingDraftCommand,
    DecisionMarkdownExport,
    ReplaceWorkingDraftCommand,
)
from ...errors import InfrastructureFailure, LineageBroken, StateConflict, UnknownRecord
from ...ports import RevisionPayloadStore, SnapshotPayload, TransactionManager
from ...ports.application_intake import AuditLogWriter
from ...ports.artifact_catalog import ArtifactCatalog
from ...ports.decision_store import DecisionStore
from ...ports.drafts import DraftHistoryApplicationReader, DraftLifecycleStore
from ...ports.transactions import WriteTransaction
from .inputs import require_working_version


class DraftHistoryService:
    def __init__(
        self,
        *,
        transactions: TransactionManager,
        drafts: DraftLifecycleStore,
        catalog: ArtifactCatalog,
        decisions: DecisionStore,
        audit: AuditLogWriter,
        payloads: RevisionPayloadStore,
        applications: DraftHistoryApplicationReader,
    ):
        self.transactions = transactions
        self.drafts = drafts
        self.catalog = catalog
        self.decisions = decisions
        self.audit = audit
        self.revision_payloads = payloads
        self.applications = applications

    def _working(self, working_draft_id: str, expected_version: int) -> WorkingDraft:
        with self.transactions.read() as tx:
            try:
                working = self.drafts.working_draft(tx, working_draft_id)
            except UnknownRecord as exc:
                raise UnknownRecord(f"unknown working draft: {working_draft_id}") from exc
        require_working_version(working, expected_version)
        return working

    def load_active_application(self, application_id: str):
        with self.transactions.read() as tx:
            application = self.applications.history_application(tx, application_id)
        if application.deleted_at is not None:
            raise StateConflict(f"application is deleted: {application_id}")
        return application

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
                working.application_id, working.id, working.edit_version, structured_json
            )
        except FileExistsError as exc:
            raise StateConflict(
                f"working draft {working.id} version {working.edit_version} is already archived: {exc}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise InfrastructureFailure(f"could not archive the working draft: {exc}") from exc

    def register_draft_snapshot(
        self, working: WorkingDraft, payload: SnapshotPayload, tx: WriteTransaction
    ) -> str:
        """Register one archived draft payload as an immutable artifact version."""
        draft = working.source
        return self.catalog.register_artifact_version(
            tx,
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
        self.load_active_application(working.application_id)
        payload = self.materialize_draft_snapshot(working)
        now = utc_now()
        with self.transactions.write() as tx:
            artifact_version_id = self.register_draft_snapshot(working, payload, tx)
            self.drafts.deactivate_working_draft(tx, working.id, working.edit_version)
            self.audit.insert_audit(
                tx,
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
                ),
            )
            self.drafts.record_event(
                tx,
                working.application_id,
                "working_draft_archived",
                {
                    "working_draft_id": working.id,
                    "edit_version": working.edit_version,
                    "artifact_version_id": artifact_version_id,
                },
            )
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
        with self.transactions.read() as tx:
            records = self.catalog.artifact_versions(tx, working.application_id)
        for record in records:
            if record["artifact_type"] != "working_draft_snapshot":
                continue
            metadata = json.loads(record["metadata_json"] or "{}")
            if not (
                metadata.get("working_draft_id") == working.id
                and metadata.get("edit_version") == working.edit_version
                and (metadata.get("content_hash") == working.content_hash)
            ):
                continue
            state = self.revision_payloads.verify_payload(record["path"], record["content_hash"])
            if state == "ok":
                return record
            raise StateConflict(
                f"the historical snapshot of working draft {working.id} version {working.edit_version} is {state}; the replacement is refused rather than run against a copy that cannot be trusted"
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
                f"working draft {working.id} does not belong to application {command.application_id}"
            )
        if not command.keep_previous:
            return working
        if self._kept_snapshot(working) is not None:
            return working
        payload = self.materialize_draft_snapshot(working)
        with self.transactions.write() as tx:
            artifact_version_id = self.register_draft_snapshot(working, payload, tx)
            self.audit.insert_audit(
                tx,
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
                ),
            )
        return working

    def export_decision_markdown(
        self, application_id: str, approved_revision_id: str
    ) -> DecisionMarkdownExport:
        """Render human-readable provenance for one explicitly named revision."""
        try:
            with self.transactions.read() as tx:
                application = self.applications.history_application(tx, application_id)
                revision = self.drafts.approved_revision(tx, approved_revision_id)
                decision = self.decisions.decision_for_revision(tx, approved_revision_id)
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
        overrides = structured.get("user_overrides") or {}

        def value(item: object) -> str:
            if isinstance(item, (dict, list)):
                return json.dumps(item, ensure_ascii=False, sort_keys=True)
            return str(item)

        lines = [
            "# CV Decision and Provenance",
            "",
            f"- Application: {application.company} — {application.target_role}",
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
                "## Overrides",
                "",
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
        for key in ("actor_type", "client", "command"):
            lines.append(f"- {key}: {revision.decision_provenance.get(key, '')}")
        content = "\n".join(lines) + "\n"
        return DecisionMarkdownExport(
            application_id=application_id,
            approved_revision_id=approved_revision_id,
            filename=f"decision-{approved_revision_id}.md",
            content=content,
            content_hash=sha256_text(content),
        )
