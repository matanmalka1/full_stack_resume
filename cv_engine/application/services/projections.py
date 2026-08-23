from __future__ import annotations

from datetime import date
from typing import cast

from ..artifacts import verify_artifact
from ..errors import (
    # Re-exported: the v1 CLI and test suite catch WorkflowError from here, and
    # it is bound to the taxonomy's base class, so every refusal below is caught.
    InfrastructureFailure,
    UnknownRecord,
)
from ..ports import (
    QueryRepository,
    ReadinessRepository,
)
from ..queries import (
    ApplicationDetailView,
    ApplicationListView,
    ApprovedRevisionView,
    ArtifactVersionDetailView,
    ArtifactVersionsView,
    DecisionRecordView,
    WorkingDraftView,
    analysis_view,
    application_list_item_view,
    application_view,
    approved_revision_view,
    artifact_version_view,
    decision_view,
    snapshot_view,
)
from ..ready import qualify_ready_revision
from ..state import ProjectionContext, project_application_state
from .base import ServiceBase


class ApplicationQueryService(ServiceBase[QueryRepository]):
    """Storage-neutral read projections for CLI, API, and future UI clients."""

    def _state_inputs(self, transaction, application_record, knowledge):
        application_id = application_record["id"]
        snapshot_record = transaction.latest_snapshot(application_id)
        analyses = transaction.analyses(application_id)
        active_analysis_record = next(
            (
                record
                for record in reversed(analyses)
                if record["job_snapshot_id"] == snapshot_record["id"]
            ),
            None,
        )
        active_analysis_id = (
            active_analysis_record["id"] if active_analysis_record is not None else None
        )
        try:
            latest_plan = transaction.latest_selection_plan(application_id)
        except UnknownRecord:
            latest_plan = None
        active_plan = (
            latest_plan
            if latest_plan is not None and latest_plan.job_analysis_id == active_analysis_id
            else None
        )
        try:
            working = transaction.active_working_draft(application_id)
        except UnknownRecord:
            working = None
        draft_plan = (
            transaction.selection_plan(working.selection_plan_id) if working is not None else None
        )
        validation = (
            transaction.latest_validation_for_working_draft(working.id)
            if working is not None
            else None
        )
        revisions = tuple(transaction.approved_revisions(application_id))
        ready_ids = frozenset(
            revision.id
            for revision in revisions
            if qualify_ready_revision(
                self.artifacts,
                transaction,
                application_id,
                approved_revision_id=revision.id,
            ).ready_qualified
        )
        active_operation = transaction.active_operation(application_id)
        state = project_application_state(
            ProjectionContext(
                application=application_record,
                active_job_snapshot_id=snapshot_record["id"],
                active_analysis_id=active_analysis_id,
                active_analysis=(
                    active_analysis_record["analysis"]
                    if active_analysis_record is not None
                    else None
                ),
                active_selection_plan=active_plan,
                draft_selection_plan=draft_plan,
                active_working_draft=working,
                latest_validation=validation,
                approved_revisions=revisions,
                ready_revision_ids=ready_ids,
                knowledge=knowledge,
                today=date.today(),
                active_operation=active_operation,
            )
        )
        return state, snapshot_record, analyses

    def list_applications(self) -> ApplicationListView:
        knowledge = self.load_knowledge()
        try:
            with self.repo.read_transaction() as transaction:
                items = []
                for row in transaction.list_applications():
                    state, _, _ = self._state_inputs(transaction, row, knowledge)
                    items.append(application_list_item_view(row, state))
                return ApplicationListView(items=items)
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored application projection is invalid: {exc}") from exc

    def application_detail(self, application_id: str) -> ApplicationDetailView:
        knowledge = self.load_knowledge()
        try:
            with self.repo.read_transaction() as transaction:
                application_record = transaction.get_application(application_id)
                application = application_view(application_record)
                state, snapshot_record, analyses = self._state_inputs(
                    transaction, application_record, knowledge
                )
                snapshot = snapshot_view(
                    snapshot_record,
                    self.snapshot_payloads.read_snapshot(
                        snapshot_record["payload_path"],
                        snapshot_record["source_hash"],
                    ),
                )
                latest = analysis_view(analyses[-1]) if analyses else None
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored application detail is invalid: {exc}") from exc
        return ApplicationDetailView(
            **state.model_dump(mode="python"),
            application=application,
            latest_snapshot=snapshot,
            latest_analysis=latest,
        )

    def artifact_versions(self, application_id: str) -> ArtifactVersionsView:
        try:
            self.repo.get_application(application_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown application: {application_id}") from exc
        try:
            return ArtifactVersionsView(
                items=[
                    artifact_version_view(row)
                    for row in self.repo.artifact_versions(application_id)
                ]
            )
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored artifact projection is invalid: {exc}") from exc

    def artifact_version(self, artifact_version_id: str) -> ArtifactVersionDetailView:
        """§20: one registered artifact's metadata and its download eligibility.

        By ID, like every other artifact surface. The stored path is read here
        and handed straight to the verification port; it never reaches the view,
        which is why the view and the detail view are the same field set plus
        three answers about availability.
        """
        try:
            record = self.repo.artifact_version(artifact_version_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown artifact version: {artifact_version_id}") from exc
        try:
            view = artifact_version_view(record)
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored artifact projection is invalid: {exc}") from exc
        availability = verify_artifact(self.revision_payloads, view, record["path"])
        return ArtifactVersionDetailView(
            **view.model_dump(mode="python"),
            downloadable=availability.downloadable,
            size=availability.size,
            unavailable_reason=availability.reason,
        )

    def approved_revision(self, approved_revision_id: str) -> ApprovedRevisionView:
        """§20: one ApprovedRevision with its Ready qualification re-derived.

        The qualification is computed here rather than read, and it is computed
        for this exact revision rather than for the Application's latest one, so
        a superseded revision reports its own truth: still qualified, still
        exportable, and no longer the active milestone.
        """
        try:
            revision = self.repo.approved_revision(approved_revision_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown approved revision: {approved_revision_id}") from exc
        # The same cast `submit_render` and `RenderOperationHandler` make.
        # Qualification reads draft lineage that `QueryRepository` does not
        # declare, and the concrete adapter satisfies `ApplicationRepository`,
        # which extends `ReadinessRepository`. Widening `QueryRepository`
        # instead would give every read projection write access to drafts.
        qualification = qualify_ready_revision(
            self.artifacts,
            cast(ReadinessRepository, self.repo),
            revision.application_id,
            revision.id,
        )
        return approved_revision_view(revision, qualification)

    def working_draft(self, working_draft_id: str) -> WorkingDraftView:
        """§20: one WorkingDraft by ID, with the token a client conditions on.

        Read by ID rather than by Application: the client that is about to
        `PATCH` one has to name the draft it is editing, and a read that
        resolved `latest` for it could hand back a different draft than the one
        the ETag it then sends was taken from.
        """
        try:
            working = self.repo.working_draft(working_draft_id)
        except UnknownRecord as exc:
            raise UnknownRecord(f"unknown working draft: {working_draft_id}") from exc
        latest = self.repo.latest_validation_for_working_draft(working_draft_id)
        exact = (
            latest
            if latest is not None
            and latest["edit_version"] == working.edit_version
            and latest["content_hash"] == working.content_hash
            else None
        )
        return WorkingDraftView(
            **working.model_dump(mode="python"),
            latest_validation_run_id=exact["id"] if exact else None,
            latest_validation_passed=exact["report"].passed if exact else None,
        )

    def latest_decision(self, application_id: str) -> DecisionRecordView:
        try:
            return decision_view(self.repo.latest_decision(application_id))
        except UnknownRecord as exc:
            raise UnknownRecord(f"no decision record for application: {application_id}") from exc
        except (TypeError, ValueError) as exc:
            raise InfrastructureFailure(f"stored decision projection is invalid: {exc}") from exc
