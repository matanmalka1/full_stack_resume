"""The approved atomic fan-in; input is immutable and all external work is finished."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from ....domain.contracts.records import AuditRecord, DecisionRecord
from ...commands import ApprovalResult
from ...ports.application_intake import AuditLogWriter
from ...ports.artifact_catalog import ArtifactCatalog
from ...ports.decision_store import DecisionStore
from ...ports.draft_lifecycle import DraftLifecycleStore
from ...ports.idempotency import IdempotencyStore
from ...ports.transactions import WriteTransaction


@dataclass(frozen=True)
class PreparedApproval:
    application_id: str
    revision_id: str
    working_draft_id: str
    validation_run_id: str
    job_snapshot_id: str
    job_analysis_id: str
    structured_reference: str
    structured_hash: str
    markdown_reference: str
    markdown_hash: str
    track: str
    profile: str
    emphasis: str
    facts_version: str
    decision_id: str
    decision_json: str
    decision_summary: str
    audit_id: str
    actor_type: Literal["user", "system"]
    client: Literal["web", "worker"]
    approved_at: str


class ApprovalCommitter:
    def __init__(
        self,
        drafts: DraftLifecycleStore,
        catalog: ArtifactCatalog,
        decisions: DecisionStore,
        audit: AuditLogWriter,
        receipts: IdempotencyStore,
    ):
        self.drafts = drafts
        self.catalog = catalog
        self.decisions = decisions
        self.audit = audit
        self.receipts = receipts

    def commit(
        self, tx: WriteTransaction, prepared: PreparedApproval, receipt_id: str | None = None
    ) -> ApprovalResult:
        p = prepared
        revision = self.drafts.create_approved_revision(
            tx,
            p.application_id,
            p.revision_id,
            p.working_draft_id,
            p.validation_run_id,
            p.structured_reference,
            p.structured_hash,
            p.markdown_reference,
            p.markdown_hash,
            {"actor_type": p.actor_type, "client": p.client, "command": "approve_draft"},
            approved_at=p.approved_at,
        )
        markdown_id = self.catalog.register_artifact_version(
            tx,
            p.application_id,
            "resume_markdown",
            "resume",
            p.markdown_reference,
            p.markdown_hash,
            "approved",
            revision_id=revision.id,
            job_snapshot_id=p.job_snapshot_id,
            track=p.track,
            profile=p.profile,
            emphasis=p.emphasis,
            facts_version=p.facts_version,
            approved_at=p.approved_at,
        )
        manifest_id = self.catalog.register_artifact_version(
            tx,
            p.application_id,
            "claim_manifest",
            "resume-claims",
            p.structured_reference,
            p.structured_hash,
            "approved",
            revision_id=revision.id,
            job_snapshot_id=p.job_snapshot_id,
            track=p.track,
            profile=p.profile,
            emphasis=p.emphasis,
            facts_version=p.facts_version,
            approved_at=p.approved_at,
        )
        self.decisions.insert_decision(
            tx,
            DecisionRecord(
                id=p.decision_id,
                application_id=p.application_id,
                artifact_version_id=markdown_id,
                job_snapshot_id=p.job_snapshot_id,
                job_analysis_id=p.job_analysis_id,
                structured=json.loads(p.decision_json),
                summary=p.decision_summary,
                created_at=p.approved_at,
            ),
        )
        self.audit.insert_audit(
            tx,
            AuditRecord(
                id=p.audit_id,
                application_id=p.application_id,
                action="approve_draft",
                entity_type="approved_revision",
                entity_id=revision.id,
                actor_type=p.actor_type,
                client=p.client,
                occurred_at=p.approved_at,
                details={
                    "decision_record_id": p.decision_id,
                    "validation_run_id": p.validation_run_id,
                },
            ),
        )
        self.drafts.record_event(
            tx,
            p.application_id,
            "draft_approved",
            {
                "approved_revision_id": revision.id,
                "decision_record_id": p.decision_id,
                "version": revision.version_number,
            },
        )
        result = ApprovalResult(
            application_id=p.application_id,
            revision_id=revision.id,
            version=revision.version_number,
            markdown_artifact_version_id=markdown_id,
            manifest_artifact_version_id=manifest_id,
            decision_record_id=p.decision_id,
        )
        if receipt_id is not None:
            self.receipts.complete_idempotency_receipt(
                tx, receipt_id, result.model_dump(mode="json")
            )
        return result
